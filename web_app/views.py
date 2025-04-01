from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
import json
import requests
import os
import time
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from .forms import CallRequestForm
from urllib.parse import quote
import urllib.parse
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib import messages
from .forms import SignupForm, LoginForm
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Twilio credentials
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_phone_number = os.getenv("TWILIO_PHONE_NUMBER")

# ElevenLabs API details
API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")
TTS_URL = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"

# Ngrok URL
NGROK_URL = os.getenv("NGROK_URL")

def text_to_speech(text):
    headers = {
        "Accept": "audio/mpeg",     
        "Content-Type": "application/json",
        "xi-api-key": API_KEY
    }

    data = {
        "text": text,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.5
        }
    }

    response = requests.post(TTS_URL, json=data, headers=headers)

    if response.status_code == 200:
        return response.content
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return None

def serve_mp3(request):
    message = request.GET.get('message', 'This is a test message.')
    message = urllib.parse.unquote(message).strip()

    mp3_content = text_to_speech(message)
    if mp3_content:
        response = HttpResponse(mp3_content, content_type="audio/mpeg")
        response['Content-Disposition'] = 'inline; filename="output.mp3"'
        return response
    else:
        return HttpResponse("Failed to generate audio.", status=500)

def initiate_call(phone_number, message):
    # Generate the MP3 file for the message
    text_to_speech(message)
    
    # Initiate Twilio call
    client = Client(account_sid, auth_token)
    encoded_message = quote(message)
    call = client.calls.create(
        url=f"{NGROK_URL}/voice/?message={encoded_message}",
        to=phone_number,
        from_=twilio_phone_number
    )

    return call.sid

def call_request(request):
    if request.method == 'POST':
        form = CallRequestForm(request.POST)
        if form.is_valid():
            phone_number = form.cleaned_data['phone_number']
            message = form.cleaned_data['message']
            
            # Clear previous recording file
            recording_file_path = os.path.join(settings.BASE_DIR, 'latest_recording.txt')
            if os.path.exists(recording_file_path):
                with open(recording_file_path, 'w') as f:
                    f.write("PENDING_NEW_RECORDING")
            
            # Store call timestamp in session
            request.session['call_timestamp'] = int(time.time())
            
            # Initiate the call
            call_sid = initiate_call(phone_number, message)
            request.session['call_sid'] = call_sid
            
            return redirect('success')
    else:
        form = CallRequestForm()
    return render(request, 'call_request.html', {'form': form})

@csrf_exempt
def voice(request):
    response = VoiceResponse()
    
    # Get message from request
    message = request.GET.get('message', 'This is a test message.')
    message = urllib.parse.unquote(message)

    # Play message audio
    mp3_url = f"{NGROK_URL}/output.mp3?message={urllib.parse.quote(message)}"
    response.play(mp3_url)

    # Record the call
    action_url = f"{NGROK_URL}/handle-recording/"
    response.record(action=action_url, max_length=30, finish_on_key="*")

    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def handle_recording(request):
    # Extract recording SID from request
    recording_sid = None
    
    if request.method == "POST" and request.headers.get('Content-Type') == 'application/json':
        try:
            data = json.loads(request.body)
            recording_sid = data.get('RecordingSid')
        except json.JSONDecodeError:
            recording_sid = None
    else:
        recording_sid = request.POST.get("RecordingSid")
    
    if not recording_sid:
        return JsonResponse({"success": False, "error": "Recording SID not found"})
    
    # Twilio recording URL
    recording_url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Recordings/{recording_sid}.mp3"

    # Ensure media directory exists
    media_directory = settings.MEDIA_ROOT
    os.makedirs(media_directory, exist_ok=True)

    filename = f"recording_{recording_sid}.mp3"
    file_path = os.path.join(media_directory, filename)
    
    # Check if file already exists
    if os.path.exists(file_path):
        public_download_url = f"{NGROK_URL}/media/{filename}"
        
        with open(os.path.join(settings.BASE_DIR, 'latest_recording.txt'), 'w') as f:
            f.write(public_download_url)
        
        return JsonResponse({"success": True, "download_url": public_download_url})

    # Retry logic for recording availability
    max_retries = 10
    retry_delay = 5

    for attempt in range(max_retries):
        response = requests.get(recording_url, auth=(account_sid, auth_token))

        if response.status_code == 200:
            # Save recording locally
            with open(file_path, "wb") as f:
                f.write(response.content)

            # Save download URL to file
            public_download_url = f"{NGROK_URL}/media/{filename}"
            recording_file_path = os.path.join(settings.BASE_DIR, 'latest_recording.txt')
            
            with open(recording_file_path, 'w') as f:
                f.write(public_download_url)
            
            # Update file timestamp
            current_time = time.time()
            os.utime(recording_file_path, (current_time, current_time))
            
            return JsonResponse({"success": True, "download_url": public_download_url})
        else:
            time.sleep(retry_delay)
    
    return JsonResponse({"success": False, "error": "Recording not available after multiple attempts"})

def success(request):
    if request.GET.get('check_file') == 'true':
        try:
            recording_file_path = os.path.join(settings.BASE_DIR, 'latest_recording.txt')
            if not os.path.exists(recording_file_path):
                return JsonResponse({"download_url": None})
                
            with open(recording_file_path, 'r') as f:
                download_url = f.read().strip()
            
            if download_url == "PENDING_NEW_RECORDING":
                return JsonResponse({"download_url": None})
                
            file_modification_time = os.path.getmtime(recording_file_path)
            session_start_time = request.session.get('call_timestamp', 0)
            
            if file_modification_time >= session_start_time:
                return JsonResponse({"download_url": download_url})
            else:
                return JsonResponse({"download_url": None})
            
        except Exception as e:
            return JsonResponse({"error": str(e)})
    
    return render(request, 'success.html', {'download_url': ''})

def signup_view(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Signup successful! Please log in.")
            return redirect('login')
        else:
            messages.error(request, "Signup failed. Please correct the errors.")
    else:
        form = SignupForm()
    return render(request, 'signup.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)  
        if form.is_valid():
            user = form.get_user()  
            login(request, user)
            messages.success(request, "Login successful!")  
            return redirect('/')  
        else:
            messages.error(request, "Invalid username or password.")  
    else:
        form = LoginForm()
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")  
    return redirect('login')
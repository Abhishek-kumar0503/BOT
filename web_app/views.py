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
from django.contrib.auth.decorators import login_required
from datetime import datetime

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

# Add this function to your views.py
def transcribe_with_assemblyai(audio_url):
    """Transcribe audio using AssemblyAI API"""
    api_key = os.getenv("ASSEMBLYAI_API_KEY")
    print(f"🔑 AssemblyAI API key: {api_key}")
    
    if not api_key:
        print("❌ AssemblyAI API key not found in environment variables")
        return "API key not configured"
    
    headers = {
        "authorization": api_key,
        "content-type": "application/json"
    }
    
    # Create transcription request
    data = {
        "audio_url": audio_url,
        "language_code": "en"  # You can change language code if needed
    }
    
    # Submit transcription request
    try:
        print(f"🎤 Submitting {audio_url} for transcription...")
        response = requests.post(
            "https://api.assemblyai.com/v2/transcript", 
            json=data, 
            headers=headers
        )
        
        if response.status_code != 200:
            print(f"❌ AssemblyAI error: {response.text}")
            return "Transcription request failed"
        
        transcript_id = response.json()["id"]
        print(f"✅ Transcription job submitted with ID: {transcript_id}")
        
        # Poll for completion
        polling_endpoint = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
        max_retries = 30  # Maximum number of polling attempts (90 seconds total)
        
        for attempt in range(max_retries):
            print(f"🔄 Checking transcription status (attempt {attempt+1}/{max_retries})")
            polling_response = requests.get(polling_endpoint, headers=headers)
            
            if polling_response.status_code != 200:
                print(f"❌ Error checking transcription status: {polling_response.text}")
                return "Error checking transcription status"
            
            status = polling_response.json()["status"]
            
            if status == "completed":
                text = polling_response.json()["text"]
                print(f"✅ Transcription completed: {text[:100]}...")
                return text
            elif status == "error":
                error_message = polling_response.json().get("error", "Unknown error")
                print(f"❌ AssemblyAI transcription error: {error_message}")
                return f"Transcription error: {error_message}"
            
            time.sleep(3)  # Wait before checking again
        
        return "Transcription timed out"
    except Exception as e:
        print(f"❌ Exception during transcription: {str(e)}")
        return f"Transcription exception: {str(e)}"

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

# @login_required(login_url='login')
def call_request(request):
    if request.method == 'POST':
        # Check if user is logged in when they try to submit the form
        if not request.user.is_authenticated:
            # Save the intended URL in session so user returns after login
            request.session['next'] = request.path
            messages.info(request, "Please login to make a call")
            return redirect('login')

        form = CallRequestForm(request.POST)
        if form.is_valid():
            call_request = form.save(commit=False)
            if request.user.is_authenticated:
                call_request.user = request.user
            call_request.save()
            
            phone_number = form.cleaned_data['phone_number']
            message = form.cleaned_data['message']
            
            # Clear previous recording file
            recording_file_path = os.path.join(settings.BASE_DIR, 'latest_recording.txt')
            if os.path.exists(recording_file_path):
                with open(recording_file_path, 'w') as f:
                    f.write("PENDING_NEW_RECORDING")
            
            # Store call timestamp and call_request_id in session
            request.session['call_timestamp'] = int(time.time())
            request.session['call_request_id'] = call_request.id
            
            # IMPORTANT: Save session explicitly
            request.session.save()
            print(f"Saved call_request_id={call_request.id} to session")
            
            # Initiate the call
            call_sid = initiate_call(phone_number, message)
            request.session['call_sid'] = call_sid
            request.session.save()  # Save again after setting call_sid
            
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
        print("⚠️ No recording SID found in request")
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
        
        # Update all existing CallRequest objects that are waiting for recordings
        from .models import CallRequest
        try:
            # Get all recent call requests (last 24 hours) without recording URLs
            recent_time = time.time() - (24 * 60 * 60)  # Last 24 hours
            recent_calls = CallRequest.objects.filter(
                recording_url__isnull=True,
                created_at__gte=datetime.fromtimestamp(recent_time)
            ).order_by('-created_at')
            
            if recent_calls.exists():
                recent_call = recent_calls.first()
                recent_call.recording_url = public_download_url
                recent_call.save()
                print(f"✅ Updated most recent call with recording URL: {public_download_url}")
        except Exception as e:
            print(f"❌ Error finding recent calls: {e}")
        
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
            
            # Transcribe the audio using AssemblyAI
            print("🎧 Starting transcription with AssemblyAI...")
            transcription = transcribe_with_assemblyai(public_download_url)
            print(f"📝 Transcription result: {transcription[:100]}...")  # Print first 100 chars of transcription
            
            # Update CallRequest with the recording URL and transcription
            call_request_id = request.session.get('call_request_id')
            print(f"📞 Call request ID from session: {call_request_id}")
            
            if call_request_id:
                from .models import CallRequest
                try:
                    call_request = CallRequest.objects.get(id=call_request_id)
                    call_request.recording_url = public_download_url
                    call_request.transcription = transcription  # Save transcription to database
                    call_request.save()
                    print(f"✅ Saved recording URL and transcription to database")
                except Exception as e:
                    print(f"❌ Error updating CallRequest: {e}")
            else:
                print("⚠️ No call_request_id found in session")
            
            # Update file timestamp
            current_time = time.time()
            os.utime(recording_file_path, (current_time, current_time))
            print(f"💿 Recording saved to {public_download_url}")
            return JsonResponse({"success": True, "download_url": public_download_url})
        else:
            print(f"⏳ Attempt {attempt+1}/{max_retries}: Recording not ready yet")
            time.sleep(retry_delay)
    
    print("❌ Failed to retrieve recording after maximum retries")
    return JsonResponse({"success": False, "error": "Recording not available after multiple attempts"})

def success(request):
    context = {}
    
    # Handle AJAX requests checking for file
    if request.GET.get('check_file') == 'true':
        recording_file_path = os.path.join(settings.BASE_DIR, 'latest_recording.txt')
        if os.path.exists(recording_file_path):
            with open(recording_file_path, 'r') as f:
                download_url = f.read().strip()
                if download_url and download_url != "PENDING_NEW_RECORDING":
                    # IMPORTANT: When recording is ready, update the most recent call record
                    try:
                        from .models import CallRequest
                        # First try with session
                        call_request_id = request.session.get('call_request_id')
                        updated = False
                        
                        if call_request_id:
                            try:
                                call_request = CallRequest.objects.get(id=call_request_id)
                                call_request.recording_url = download_url
                                call_request.save()
                                print(f"✅ Updated recording URL via session: {download_url}")
                                updated = True
                            except Exception as e:
                                print(f"❌ Error updating via session: {e}")
                                
                        # If that fails, find the most recent call without a recording
                        if not updated and request.user.is_authenticated:
                            recent_calls = CallRequest.objects.filter(
                                user=request.user,
                                recording_url__isnull=True
                            ).order_by('-created_at')
                            
                            if recent_calls.exists():
                                call_request = recent_calls.first()
                                call_request.recording_url = download_url
                                call_request.save()
                                print(f"✅ Updated most recent call record: {call_request.id}")
                                
                    except Exception as e:
                        print(f"❌ Error updating CallRequest: {e}")
                        
                    return JsonResponse({"success": True, "download_url": download_url})
        return JsonResponse({"success": False})
    
    # Get the most recent recording URL for display
    recording_file_path = os.path.join(settings.BASE_DIR, 'latest_recording.txt')
    current_recording_url = ""
    if os.path.exists(recording_file_path):
        with open(recording_file_path, 'r') as f:
            current_recording_url = f.read().strip()
            if current_recording_url == "PENDING_NEW_RECORDING":
                current_recording_url = ""
    
    context['current_recording_url'] = current_recording_url
    
    # Get user's call history
    if request.user.is_authenticated:
        from .models import CallRequest
        call_history = CallRequest.objects.filter(
            user=request.user
        ).order_by('-created_at')
        context['call_history'] = call_history
    
    return render(request, 'success.html', context)

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

# Update login view to redirect to 'next' URL if available
def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)  
        if form.is_valid():
            user = form.get_user()  
            login(request, user)
            messages.success(request, "Login successful!")
            # Redirect to the 'next' URL if available
            next_url = request.session.get('next', '/')
            if 'next' in request.session:
                del request.session['next']
            return redirect(next_url)
        else:
            messages.error(request, "Invalid username or password.")  
    else:
        form = LoginForm()
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")  
    return redirect('login')
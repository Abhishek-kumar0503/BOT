from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
import requests
import os
import threading
import time
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from urllib.parse import quote, unquote
from .forms import CallRequestForm, SignupForm, LoginForm
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages

# Twilio credentials
account_sid = settings.TWILIO_ACCOUNT_SID
auth_token = settings.TWILIO_AUTH_TOKEN
twilio_phone_number = settings.TWILIO_PHONE_NUMBER

# ElevenLabs API details
API_KEY = settings.ELEVENLABS_API_KEY
VOICE_ID = settings.ELEVENLABS_VOICE_ID
TTS_URL = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"

# Ngrok URL
NGROK_URL = settings.NGROK_URL

def text_to_speech(text):
    """Converts text to speech using ElevenLabs API and returns MP3 content."""
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": API_KEY
    }
    data = {"text": text, "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}}
    
    response = requests.post(TTS_URL, json=data, headers=headers)
    return response.content if response.status_code == 200 else None

def serve_mp3(request):
    """Generates and serves MP3 audio for a given message."""
    message = unquote(request.GET.get('message', 'This is a test message.')).strip()
    mp3_content = text_to_speech(message)
    
    if mp3_content:
        response = HttpResponse(mp3_content, content_type="audio/mpeg")
        response['Content-Disposition'] = 'inline; filename="output.mp3"'
        return response
    return HttpResponse("Failed to generate audio.", status=500)

def initiate_call(phone_number, message):
    """Initiates a call using Twilio and plays the generated MP3 message."""
    mp3_url = f"{NGROK_URL}/output.mp3?message={quote(message)}"
    client = Client(account_sid, auth_token)

    call = client.calls.create(
        url=f"{NGROK_URL}/voice/?message={quote(message)}",
        to=phone_number,
        from_=twilio_phone_number
    )

@csrf_exempt
def call_request(request):
    """Handles call request form submission."""
    if request.method == 'POST':
        form = CallRequestForm(request.POST)
        if form.is_valid():
            phone_number = form.cleaned_data['phone_number']
            message = form.cleaned_data['message']
            threading.Thread(target=initiate_call, args=(phone_number, message)).start()
            return redirect('success')
    else:
        form = CallRequestForm()
    return render(request, 'call_request.html', {'form': form})

@csrf_exempt
def voice(request):
    """Generates TwiML response to play the MP3 message in a call."""
    response = VoiceResponse()
    message = unquote(request.GET.get('message', 'This is a test message.'))
    mp3_url = f"{NGROK_URL}/output.mp3?message={quote(message)}"
    response.play(mp3_url)
    response.record(action=f"{NGROK_URL}/handle-recording/", max_length=30, finish_on_key="*")
    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def handle_recording(request):
    """Handles call recording and saves it locally."""
    recording_sid = request.POST.get("RecordingSid")
    if not recording_sid:
        return HttpResponse("Error: Recording SID not found.", status=400)

    recording_url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Recordings/{recording_sid}.mp3"
    media_directory = settings.MEDIA_ROOT
    os.makedirs(media_directory, exist_ok=True)

    file_path = os.path.join(media_directory, f"recording_{recording_sid}.mp3")
    
    for _ in range(6):  # Retry logic
        response = requests.get(recording_url, auth=(account_sid, auth_token))
        if response.status_code == 200:
            with open(file_path, "wb") as f:
                f.write(response.content)
            public_download_url = request.build_absolute_uri(f"{NGROK_URL}/media/{file_path}")
            return JsonResponse({"success": True, "download_url": public_download_url})
        time.sleep(5)

    return JsonResponse({"success": False, "error": "Recording not found after multiple attempts."}, status=500)

def success(request):
    """Renders the success page."""
    return render(request, 'success.html')

# Authentication Views
def signup_view(request):
    """Handles user signup."""
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Signup successful! Please log in.")
            return redirect('login')
        messages.error(request, "Signup failed. Please correct the errors.")
    else:
        form = SignupForm()
    return render(request, 'signup.html', {'form': form})

def login_view(request):
    """Handles user login."""
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            messages.success(request, "Login successful!")
            return redirect('/')
        messages.error(request, "Invalid username or password.")
    else:
        form = LoginForm()
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    """Logs the user out."""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('login')

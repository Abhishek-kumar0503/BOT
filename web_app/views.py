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
from .forms import CallRequestForm, SignupForm, LoginForm
from urllib.parse import quote
import urllib.parse
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib import messages
from dotenv import load_dotenv
from django.contrib.auth.decorators import login_required
from datetime import datetime
import assemblyai as aai
from .models import CallRequest

# Load environment variables
load_dotenv()

# API credentials
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_phone_number = os.getenv("TWILIO_PHONE_NUMBER")
API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")
TTS_URL = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
assemblyai_api_key = os.getenv("ASSEMBLYAI_API_KEY")
NGROK_URL = os.getenv("NGROK_URL")

# Replace your current transcribe_with_assemblyai function with this improved version:
def transcribe_with_assemblyai(audio_path):
    """Transcribe audio using AssemblyAI API with improved error handling"""
    try:
        aai.settings.api_key = assemblyai_api_key
        print(f"🔑 AssemblyAI API key: {assemblyai_api_key[:8]}...")
        print(f"🎤 Transcribing file at: {audio_path}")
        
        if not os.path.exists(audio_path):
            return "File not found error"
        
        # Check file size (AssemblyAI has a 1GB limit)
        file_size = os.path.getsize(audio_path)
        if file_size > 1_000_000_000:  # 1GB in bytes
            return "File too large for transcription"
        elif file_size < 1000:  # Very small files are likely invalid
            return "File too small, may not contain audio"
        
        print(f"📊 File size: {file_size/1_000_000:.2f}MB")
        
        # Try direct transcription first
        try:
            transcriber = aai.Transcriber()
            transcript = transcriber.transcribe(audio_path)
            
            if transcript and hasattr(transcript, 'text'):
                result = transcript.text
                print(f"✅ Transcription successful: {result[:100]}...")
                return result
            elif isinstance(transcript, dict) and 'text' in transcript:
                return transcript['text']
        except Exception as direct_error:
            print(f"⚠️ Direct transcription failed: {str(direct_error)}")
            # Fall through to alternative method
        
        # Alternative method: Upload file manually and then transcribe URL
        print("🔄 Trying alternative transcription method...")
        with open(audio_path, "rb") as audio_file:
            upload_url = None
            
            # Make direct upload request
            upload_response = requests.post(
                "https://api.assemblyai.com/v2/upload",
                headers={"authorization": assemblyai_api_key},
                data=audio_file
            )
            
            if upload_response.status_code == 200:
                upload_url = upload_response.json()["upload_url"]
                print(f"📤 Upload successful: {upload_url[:30]}...")
            else:
                return f"Upload failed with status {upload_response.status_code}: {upload_response.text}"
            
            # Submit for transcription using upload URL
            transcript_response = requests.post(
                "https://api.assemblyai.com/v2/transcript",
                headers={
                    "authorization": assemblyai_api_key,
                    "content-type": "application/json"
                },
                json={"audio_url": upload_url}
            )
            
            if transcript_response.status_code != 200:
                return f"Transcription request failed: {transcript_response.text}"
            
            transcript_id = transcript_response.json()["id"]
            polling_endpoint = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
            
            # Poll for results
            max_polls = 12  # 60 seconds max
            for i in range(max_polls):
                print(f"⏳ Polling for results ({i+1}/{max_polls})...")
                poll_response = requests.get(
                    polling_endpoint,
                    headers={"authorization": assemblyai_api_key}
                )
                
                if poll_response.status_code != 200:
                    return f"Polling failed: {poll_response.text}"
                
                status = poll_response.json()["status"]
                if status == "completed":
                    return poll_response.json()["text"]
                elif status == "error":
                    return f"Transcription error: {poll_response.json()['error']}"
                
                time.sleep(5)
            
            return "Transcription still in progress, please check later"
            
    except Exception as e:
        print(f"❌ Exception during transcription: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"Transcription error: {str(e)}"

def text_to_speech(text):
    headers = {
        "Accept": "audio/mpeg",     
        "Content-Type": "application/json",
        "xi-api-key": API_KEY
    }

    data = {
        "text": text,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}
    }

    response = requests.post(TTS_URL, json=data, headers=headers)
    if response.status_code == 200:
        return response.content
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return None

def serve_mp3(request):
    message = urllib.parse.unquote(request.GET.get('message', 'This is a test message.')).strip()
    mp3_content = text_to_speech(message)
    
    if mp3_content:
        response = HttpResponse(mp3_content, content_type="audio/mpeg")
        response['Content-Disposition'] = 'inline; filename="output.mp3"'
        return response
    else:
        return HttpResponse("Failed to generate audio.", status=500)

def initiate_call(phone_number, message):
    text_to_speech(message)
    client = Client(account_sid, auth_token)
    call = client.calls.create(
        url=f"{NGROK_URL}/voice/?message={quote(message)}",
        to=phone_number,
        from_=twilio_phone_number
    )
    return call.sid

def call_request(request):
    if request.method == 'POST':
        if not request.user.is_authenticated:
            request.session['next'] = request.path
            messages.info(request, "Please login to make a call")
            return redirect('login')

        form = CallRequestForm(request.POST)
        if form.is_valid():
            call_request = form.save(commit=False)
            if request.user.is_authenticated:
                call_request.user = request.user
            call_request.save()
            
            # Store call_request_id in both session and file
            call_id = call_request.id
            request.session['call_request_id'] = call_id
            
            with open(os.path.join(settings.BASE_DIR, 'latest_call_id.txt'), 'w') as f:
                f.write(str(call_id))

            # Reset recording file
            with open(os.path.join(settings.BASE_DIR, 'latest_recording.txt'), 'w') as f:
                f.write("PENDING_NEW_RECORDING")
            
            # Store call info in session
            request.session['call_timestamp'] = int(time.time())
            request.session.save()
            print(f"Saved call_request_id={call_request.id} to session")
            
            # Initiate call
            call_sid = initiate_call(form.cleaned_data['phone_number'], form.cleaned_data['message'])
            request.session['call_sid'] = call_sid
            request.session.save()
            
            return redirect('success')
    else:
        form = CallRequestForm()
    return render(request, 'call_request.html', {'form': form})

@csrf_exempt
def voice(request):
    response = VoiceResponse()
    message = urllib.parse.unquote(request.GET.get('message', 'This is a test message.'))
    mp3_url = f"{NGROK_URL}/output.mp3?message={urllib.parse.quote(message)}"
    response.play(mp3_url)
    response.record(action=f"{NGROK_URL}/handle-recording/", max_length=30, finish_on_key="*")
    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def handle_recording(request):
    # Get recording SID
    recording_sid = None
    
    if request.method == "POST" and request.headers.get('Content-Type') == 'application/json':
        try:
            recording_sid = json.loads(request.body).get('RecordingSid')
        except json.JSONDecodeError:
            pass
    else:
        recording_sid = request.POST.get("RecordingSid")
    
    if not recording_sid:
        return JsonResponse({"success": False, "error": "Recording SID not found"})
    
    # Set up file paths
    recording_url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Recordings/{recording_sid}.mp3"
    media_directory = settings.MEDIA_ROOT
    os.makedirs(media_directory, exist_ok=True)
    filename = f"recording_{recording_sid}.mp3"
    file_path = os.path.join(media_directory, filename)
    
    # Check if file already exists
    if os.path.exists(file_path):
        public_download_url = f"{NGROK_URL}/media/{filename}"
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

            # Save download URL and update timestamp
            public_download_url = f"{NGROK_URL}/media/{filename}"
            # recording_file_path = os.path.join(settings.BASE_DIR, 'latest_recording.txt')
            # with open(recording_file_path, 'w') as f:
            #     f.write(public_download_url)
            
            # Get transcription
            print("🎧 Starting transcription with AssemblyAI...")
            try:
                transcription = transcribe_with_assemblyai(file_path)
            except Exception as e:
                transcription = f"Transcription failed: {str(e)}"
            
            # Save transcription to file
            with open(os.path.join(settings.BASE_DIR, 'latest_transcription.txt'), 'w') as f:
                f.write(transcription)
                
            # Find the right call record to update
            updated = False
            
            # Try from call ID file
            try:
                call_id_file = os.path.join(settings.BASE_DIR, 'latest_call_id.txt')
                if os.path.exists(call_id_file):
                    with open(call_id_file, 'r') as f:
                        file_call_id = f.read().strip()
                        
                    if file_call_id and file_call_id.isdigit():
                        call_request = CallRequest.objects.get(id=int(file_call_id))
                        call_request.recording_url = public_download_url
                        call_request.transcription = transcription
                        call_request.save()
                        print(f"✅ Updated via file ID: {file_call_id}")
                        updated = True
            except Exception as e:
                print(f"❌ Error updating via file ID: {e}")

            # If that fails, try most recent record
            if not updated:
                try:
                    recent_call = CallRequest.objects.filter(recording_url__isnull=True).order_by('-created_at').first()
                    if recent_call:
                        recent_call.recording_url = public_download_url
                        recent_call.transcription = transcription
                        recent_call.save()
                        print(f"✅ Updated most recent call: {recent_call.id}")
                        updated = True
                except Exception as e:
                    print(f"❌ Error updating recent call: {e}")
            
            return JsonResponse({
                "success": True, 
                "download_url": public_download_url,
                "transcription": transcription
            })
        else:
            print(f"⏳ Attempt {attempt+1}/{max_retries}: Recording not ready yet")
            time.sleep(retry_delay)
    
    return JsonResponse({"success": False, "error": "Recording not available after multiple attempts"})

def success(request):
    context = {}
    
    if request.GET.get('check_file') == 'true':
        try:
            # First try from session
            call_request_id = request.session.get('call_request_id')
            print(f"Checking for recording with call_request_id: {call_request_id}")
            
            if call_request_id:
                try:
                    call_request = CallRequest.objects.get(id=call_request_id)
                    
                    if call_request.recording_url:
                        print(f"Found recording URL: {call_request.recording_url}")
                        return JsonResponse({
                            "success": True, 
                            "download_url": call_request.recording_url,
                            "transcription": call_request.transcription or ""
                        })
                    else:
                        print("Call record found but no recording URL yet")
                except CallRequest.DoesNotExist:
                    print(f"No call request found with ID: {call_request_id}")
            
            # As a fallback, check the latest_recording.txt file directly
            recording_file_path = os.path.join(settings.BASE_DIR, 'latest_recording.txt')
            if os.path.exists(recording_file_path):
                with open(recording_file_path, 'r') as f:
                    download_url = f.read().strip()
                    if download_url and download_url != "PENDING_NEW_RECORDING":
                        print(f"Found recording from file: {download_url}")
                        return JsonResponse({"success": True, "download_url": download_url})
            
            print("No recording found yet")
            return JsonResponse({"success": False})
        except Exception as e:
            print(f"Error in check_file handler: {e}")
            return JsonResponse({"success": False, "error": str(e)})
            return JsonResponse({"success": False})
    
    # Get most recent call for current user
    current_call = None
    if request.user.is_authenticated:
        current_call = CallRequest.objects.filter(user=request.user).order_by('-created_at').first()
        
    if current_call:
        context['current_recording_url'] = current_call.recording_url or ""
    else:
        context['current_recording_url'] = ""
    
    # Get user's call history
    if request.user.is_authenticated:
        context['call_history'] = CallRequest.objects.filter(user=request.user).order_by('-created_at')
    
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

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)  
        if form.is_valid():
            user = form.get_user()  
            login(request, user)
            messages.success(request, "Login successful!")
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
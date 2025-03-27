# from django.shortcuts import render, redirect
# from django.http import HttpResponse, JsonResponse
# import requests
# import os
# import threading
# import time
# from twilio.rest import Client
# from twilio.twiml.voice_response import VoiceResponse
# from django.conf import settings
# from django.views.decorators.csrf import csrf_exempt
# from urllib.parse import quote, unquote
# from .forms import CallRequestForm, SignupForm, LoginForm
# from django.contrib.auth import login, authenticate, logout
# from django.contrib import messages
# from dotenv import load_dotenv

# # Load environment variables
# load_dotenv()

# # Twilio credentials
# account_sid = os.getenv("TWILIO_ACCOUNT_SID")
# auth_token = os.getenv("TWILIO_AUTH_TOKEN")
# twilio_phone_number = os.getenv("TWILIO_PHONE_NUMBER")

# # ElevenLabs API details
# API_KEY = os.getenv("ELEVENLABS_API_KEY")
# VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")
# TTS_URL = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"

# # Ngrok URL
# NGROK_URL = os.getenv("NGROK_URL")

# # print(f"TWILIO_ACCOUNT_SID: {account_sid}")
# # print(f"TWILIO_AUTH_TOKEN: {auth_token}")
# # print(f"TWILIO_PHONE_NUMBER: {twilio_phone_number}")
# # print(f"11labs: {API_KEY}")
# # print(f"Voice IDs: {VOICE_ID}")

# def text_to_speech(text):
#     """Converts text to speech using ElevenLabs API and returns MP3 content."""
#     headers = {
#         "Accept": "audio/mpeg",
#         "Content-Type": "application/json",
#         "xi-api-key": API_KEY
#     }
#     data = {"text": text, "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}}
    
#     response = requests.post(TTS_URL, json=data, headers=headers)
#     return response.content if response.status_code == 200 else None

# def serve_mp3(request):
#     """Generates and serves MP3 audio for a given message."""
#     message = unquote(request.GET.get('message', 'This is a test message.')).strip()
#     mp3_content = text_to_speech(message)
    
#     if mp3_content:
#         response = HttpResponse(mp3_content, content_type="audio/mpeg")
#         response['Content-Disposition'] = 'inline; filename="output.mp3"'
#         return response
#     return HttpResponse("Failed to generate audio.", status=500)

# def initiate_call(phone_number, message):
#     """Initiates a call using Twilio and plays the generated MP3 message."""
#     mp3_url = f"{NGROK_URL}/output.mp3?message={quote(message)}"
#     client = Client(account_sid, auth_token)

#     call = client.calls.create(
#         url=f"{NGROK_URL}/voice/?message={quote(message)}",
#         to=phone_number,
#         from_=twilio_phone_number
#     )

# @csrf_exempt
# def call_request(request):
#     """Handles call request form submission."""
#     if request.method == 'POST':
#         form = CallRequestForm(request.POST)
#         if form.is_valid():
#             phone_number = form.cleaned_data['phone_number']
#             message = form.cleaned_data['message']
#             threading.Thread(target=initiate_call, args=(phone_number, message)).start()
#             return redirect('success')
#     else:
#         form = CallRequestForm()
#     return render(request, 'call_request.html', {'form': form})

# @csrf_exempt
# def voice(request):
#     """Generates TwiML response to play the MP3 message in a call."""
#     response = VoiceResponse()
#     message = unquote(request.GET.get('message', 'This is a test message.'))
#     mp3_url = f"{NGROK_URL}/output.mp3?message={quote(message)}"
#     response.play(mp3_url)
#     response.record(action=f"{NGROK_URL}/handle-recording/", max_length=30, finish_on_key="*")
#     return HttpResponse(str(response), content_type="text/xml")

# @csrf_exempt
# def handle_recording(request):
#     """Handles call recording and saves it locally."""
#     recording_sid = request.POST.get("RecordingSid")
#     if not recording_sid:
#         return HttpResponse("Error: Recording SID not found.", status=400)

#     recording_url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Recordings/{recording_sid}.mp3"
#     media_directory = settings.MEDIA_ROOT
#     os.makedirs(media_directory, exist_ok=True)

#     file_path = os.path.join(media_directory, f"recording_{recording_sid}.mp3")
    
#     for _ in range(6):  # Retry logic
#         response = requests.get(recording_url, auth=(account_sid, auth_token))
#         if response.status_code == 200:
#             with open(file_path, "wb") as f:
#                 f.write(response.content)
#             public_download_url = request.build_absolute_uri(f"{NGROK_URL}/media/{file_path}")
#             print(public_download_url)
#             return JsonResponse({"success": True, "download_url": public_download_url})
#         time.sleep(5)

#     return JsonResponse({"success": False, "error": "Recording not found after multiple attempts."}, status=500)

# def success(request):
#     """Renders the success page."""
#     return render(request, 'success.html')

# # Authentication Views
# def signup_view(request):
#     """Handles user signup."""
#     if request.method == 'POST':
#         form = SignupForm(request.POST)
#         if form.is_valid():
#             user = form.save()
#             login(request, user)
#             messages.success(request, "Signup successful! Please log in.")
#             return redirect('login')
#         messages.error(request, "Signup failed. Please correct the errors.")
#     else:
#         form = SignupForm()
#     return render(request, 'signup.html', {'form': form})

# def login_view(request):
#     """Handles user login."""
#     if request.method == 'POST':
#         form = LoginForm(request, data=request.POST)
#         if form.is_valid():
#             login(request, form.get_user())
#             messages.success(request, "Login successful!")
#             return redirect('/')
#         messages.error(request, "Invalid username or password.")
#     else:
#         form = LoginForm()
#     return render(request, 'login.html', {'form': form})

# def logout_view(request):
#     """Logs the user out."""
#     logout(request)
#     messages.info(request, "You have been logged out.")
#     return redirect('login')

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
from django.contrib import messages  # ✅ Import messages for notifications
from .forms import SignupForm, LoginForm

# # Twilio credentials
# account_sid = 'ACcf6c1f1878da70d14d3f1508e27921fe'
# auth_token = 'ad1b02b29bd3c1e22e6f4b62e3bcf461'
# twilio_phone_number = "+18573416336"

# # ElevenLabs API details
# API_KEY = "sk_a3c8b57009510c4873c66ad71bc8669ff32f995b6f9e5759"
# VOICE_ID = "21m00Tcm4TlvDq8ikWAM"
# TTS_URL = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"

# # Ngrok URL (update this with your Ngrok URL)
# NGROK_URL = "https://cfb8-103-69-14-55.ngrok-free.app"  # 🚨 Replace with your Ngrok URL

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
# print(f"TWILIO_ACCOUNT_SID: {account_sid}")
# print(f"TWILIO_AUTH_TOKEN: {auth_token}")
# print(f"TWILIO_PHONE_NUMBER: {twilio_phone_number}")
# print(f"11labs: {API_KEY}")
# print(f"Voice IDs: {VOICE_ID}")
# Global flag to indicate if the recording has been saved
recording_saved = False

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

    print(f"📄 Sending request to ElevenLabs API with text: {text}")
    response = requests.post(TTS_URL, json=data, headers=headers)

    if response.status_code == 200:
        print("🎧 Audio generated successfully.")
        return response.content  # Return the MP3 content directly
    else:
        print(f"❌ Error: {response.status_code}, {response.text}")
        return None

def serve_mp3(request):
    message = request.GET.get('message', 'This is a test message.')
    message = urllib.parse.unquote(message).strip()  # Decode and strip spaces
    print(f"🎵 Serving MP3 for message: {message}")

    mp3_content = text_to_speech(message)
    if mp3_content:
        response = HttpResponse(mp3_content, content_type="audio/mpeg")
        response['Content-Disposition'] = 'inline; filename="output.mp3"'
        return response
    else:
        return HttpResponse("Failed to generate audio.", status=500)

def initiate_call(phone_number, message):
    global recording_saved
    print(f"🚀 Starting call to: {phone_number}")
    print(f"📣 Message: {message}")

    # Generate the MP3 file for the message
    text_to_speech(message)
    print("3") #printed
    # Generate the MP3 file URL with the message as a query parameter
    mp3_url = f"{NGROK_URL}/output.mp3?message={message}"
    print(f"🎧 MP3 URL: {mp3_url}")
    
    response=VoiceResponse()
    response.play(mp3_url)
    
    # Initiate Twilio call
    client = Client(account_sid, auth_token)
    print("4") #printed
    encoded_message = quote(message)
    call = client.calls.create(
        url=f"{NGROK_URL}/voice/?message={encoded_message}",  # Use Ngrok URL for Twilio webhook
        to=phone_number,
        from_=twilio_phone_number
    )

    print(f"📞 Call initiated! Call SID: {call.sid}")

    # Wait for the recording to be saved
    # while not recording_saved:
    #     time.sleep(1)
    return call.sid
<<<<<<< HEAD
    print("✅ Recording saved. Exiting...")

    temp= True
    return temp

=======
    # print("✅ Recording saved. Exiting...")

    # temp= True
    # return temp

@csrf_exempt
>>>>>>> ddc1e350f5725ad3502cddb0f3dc413050b7440d
def call_request(request):
    if request.method == 'POST':
        form = CallRequestForm(request.POST)
        if form.is_valid():
            phone_number = form.cleaned_data['phone_number']
            message = form.cleaned_data['message']

<<<<<<< HEAD
            print(f"📞 Initiating call to: {phone_number}, Message: {message}")
            
            # Important: Clear the previous recording file so we don't show old recordings
            recording_file_path = os.path.join(settings.BASE_DIR, 'latest_recording.txt')
            if os.path.exists(recording_file_path):
                # Either delete it or mark it as invalid
                with open(recording_file_path, 'w') as f:
                    f.write("PENDING_NEW_RECORDING")  # This will be recognized as not a valid URL
            
            # Store the current timestamp in session to identify this call
            request.session['call_timestamp'] = int(time.time())
            print(f"📝 New call started at timestamp: {request.session['call_timestamp']}")
            
            # Call initiate_call synchronously
            call_sid = initiate_call(phone_number, message)
            print(f"📱 Call SID: {call_sid}")
            
            # Store call_sid in session for later reference
            request.session['call_sid'] = call_sid
            
            # Redirect to success page - let the JavaScript polling handle the rest
            return redirect('success')
=======
            # Debug: Print phone number and message
            print(f"📞 Initiating call to: {phone_number}, Message: {message}")

            # Call initiate_call synchronously (no threading)
            request.call_sid = initiate_call(phone_number, message)
            # print(call_sid)
            return render(request, 'success.html')
            # target_url = f"{NGROK_URL}/handle-recording/"
            
            # data = {
            #     'RecordingSid': call_sid
            # }
            # headers = {
            #     'Content-Type': 'application/json' # or another content type if needed
            #     # 'Authorization': 'Bearer YOUR_TOKEN',  # If the target API requires auth
            # }
            # response = requests.post(target_url, json=data, headers=headers)
            # data=response.json()
            # print(response)
            # if call_sid:
            #     while 'download_url' not in data:
            #         time.sleep(1)
            #         response = requests.post(target_url, json=data, headers=headers)
            #         data=response.json()
            #     # return render(request, 'myapp/index.html', {'target_url': target_url})
            #     # download_url=request.GET.get('download_url')
            #     # {'download_url': response['download_url']}
            #     return render(request, 'success.html', {'download_url': data.get('download_url', 'No URL')})
            # else:
            #     print("Error123")
>>>>>>> ddc1e350f5725ad3502cddb0f3dc413050b7440d
    else:
        form = CallRequestForm()
    return render(request, 'call_request.html', {'form': form})

# @csrf_exempt
# def call_request(request):
#     if request.method == 'POST':
#         form = CallRequestForm(request.POST)
#         if form.is_valid():
#             phone_number = form.cleaned_data['phone_number']
#             message = form.cleaned_data['message']

#             # Debug: Print phone number and message
#             print(f"📞 Initiating call to: {phone_number}, Message: {message}")

#             # Initiate the call in a separate thread
#             threading.Thread(target=initiate_call, args=(phone_number, message)).start()

#             return redirect('success')
#     else:
#         form = CallRequestForm()
#     return render(request, 'call_request.html', {'form': form})

@csrf_exempt
def voice(request):
    response = VoiceResponse()
<<<<<<< HEAD
=======

    # Ensure we get the correct message and decode it
    message = request.GET.get('message', 'This is a test message.')
    message = urllib.parse.unquote(message)  # Decode URL-encoded text
    print(f"🔹 Received message in /voice/: {message}")

    # Generate correct MP3 URL
    mp3_url = f"{NGROK_URL}/output.mp3?message={urllib.parse.quote(message)}"
    print(f"🎧 Playing audio from URL: {mp3_url}")

    response.play(mp3_url)

    # Record the call and set the action URL
    action_url = f"{NGROK_URL}/handle-recording/"
    response.record(action=action_url, max_length=30, finish_on_key="*")

    twiml = str(response)
    print(f"📄 TwiML Response: {twiml}")

    return HttpResponse(twiml, content_type="text/xml")
>>>>>>> ddc1e350f5725ad3502cddb0f3dc413050b7440d

    # Ensure we get the correct message and decode it
    message = request.GET.get('message', 'This is a test message.')
    message = urllib.parse.unquote(message)  # Decode URL-encoded text
    print(f"🔹 Received message in /voice/: {message}")

    # Generate correct MP3 URL
    mp3_url = f"{NGROK_URL}/output.mp3?message={urllib.parse.quote(message)}"
    print(f"🎧 Playing audio from URL: {mp3_url}")

    response.play(mp3_url)

    # Record the call and set the action URL
    action_url = f"{NGROK_URL}/handle-recording/"
    response.record(action=action_url, max_length=30, finish_on_key="*")

    twiml = str(response)
    print(f"📄 TwiML Response: {twiml}")

    return HttpResponse(twiml, content_type="text/xml")
@csrf_exempt
def handle_recording(request):
    print("✅ Received request at /handle-recording")
<<<<<<< HEAD
    
    # Check for JSON data in request body (for API calls)
    if request.method == "POST" and request.headers.get('Content-Type') == 'application/json':
        try:
            data = json.loads(request.body)
            recording_sid = data.get('RecordingSid')
            print(f"📌 Received RecordingSid from JSON: {recording_sid}")
        except json.JSONDecodeError:
            recording_sid = None
    else:
        # Regular POST from Twilio webhook or GET request
        recording_sid = request.POST.get("RecordingSid")
        print(f"📌 Received RecordingSid: {recording_sid}")
    
    # Validate recording_sid
    if not recording_sid:
        print("⚠️ valid RecordingSid: None")
        return JsonResponse({"success": False, "error": "Recording SID not found"})
    
    print(f"🔗 Attempting to fetch recording from: https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Recordings/{recording_sid}.mp3")
    print(f"Recording SID: {recording_sid}")

    # Twilio recording URL (Authenticated)
    recording_url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Recordings/{recording_sid}.mp3"

    # Ensure the media directory exists
    media_directory = settings.MEDIA_ROOT
    os.makedirs(media_directory, exist_ok=True)

    filename = f"recording_{recording_sid}.mp3"
    file_path = os.path.join(media_directory, filename)
    
    # Check if the file already exists
    if os.path.exists(file_path):
        print(f"✅ Recording already saved: {filename}")
        public_download_url = f"{NGROK_URL}/media/{filename}"
        print(f"🔗 Public Download URL: {public_download_url}")
        
        # IMPORTANT: Store the download URL in a global file
        with open(os.path.join(settings.BASE_DIR, 'latest_recording.txt'), 'w') as f:
            f.write(public_download_url)
        print(f"✅ Saved URL to file: {public_download_url}")
        
        return JsonResponse({"success": True, "download_url": public_download_url})

    # Retry logic to wait for recording availability
    max_retries = 10  # Retry for 30 seconds
    retry_delay = 5   # Wait 5 seconds per attempt

    for attempt in range(max_retries):
        response = requests.get(recording_url, auth=(account_sid, auth_token))  # Authenticate request
=======

    recording_sid = None

    if request.method == 'GET':
        recording_sid = request.GET.get("RecordingSid")
    else:  # POST request from Twilio
        recording_sid = request.POST.get("RecordingSid")

    print(f"📌 Received RecordingSid: {recording_sid}")

    # Ignore invalid RecordingSid (must start with 'RE')
    if not recording_sid or not recording_sid.startswith("RE"):
        print(f"⚠️ valid RecordingSid: {recording_sid}")
        # return JsonResponse({"success": False, "error": "Invalid or missing RecordingSid"})

    # Twilio recording URL
    recording_url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Recordings/{recording_sid}.mp3"
    print(f"🔗 Attempting to fetch recording from: {recording_url}")
    print(f'Recording SID: {recording_sid}')

    # Ensure media directory exists
    media_directory = settings.MEDIA_ROOT
    print("6")
    if not os.path.exists(media_directory):
        os.makedirs(media_directory)

    filename = f"recording_{recording_sid}.mp3"
    print("7")
    file_path = os.path.join(media_directory, filename)

    # Retry logic to wait for recording availability
    max_retries = 6
    retry_delay = 5

    for attempt in range(max_retries):
        response = requests.get(recording_url, auth=(account_sid, auth_token))

>>>>>>> ddc1e350f5725ad3502cddb0f3dc413050b7440d
        if response.status_code == 200:
            # Save the recording locally
            with open(file_path, "wb") as f:
                f.write(response.content)

            print(f"✅ Recording saved: {filename}")

<<<<<<< HEAD
            # When saving the recording URL, update the file timestamp
            public_download_url = f"{NGROK_URL}/media/{filename}"
            recording_file_path = os.path.join(settings.BASE_DIR, 'latest_recording.txt')
            
            with open(recording_file_path, 'w') as f:
                f.write(public_download_url)
            
            # IMPORTANT: Explicitly update the file timestamp to current time
            current_time = time.time()
            os.utime(recording_file_path, (current_time, current_time))
            
            print(f"✅ Saved URL to file at timestamp {current_time}: {public_download_url}")
            
            print(f"📡 Response sent: {{'success': true, 'download_url': '{public_download_url}'}}")
            return JsonResponse({"success": True, "download_url": public_download_url})

        else:
            print(f"⏳ Attempt {attempt + 1}: Recording not ready yet. Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
    
    # If we reach here, all retries failed
    print("❌ Failed to retrieve recording after all retries")
    return JsonResponse({"success": False, "error": "Recording not available after multiple attempts"})


def success(request):
    # Debug output
    print(f"Success view called with: {request.GET}")
    
    # Check if this is an AJAX request to check for file existence
    if request.GET.get('check_file') == 'true':
        print("Processing check_file request")
        try:
            recording_file_path = os.path.join(settings.BASE_DIR, 'latest_recording.txt')
            if not os.path.exists(recording_file_path):
                return JsonResponse({"download_url": None})
                
            # Get file content
            with open(recording_file_path, 'r') as f:
                download_url = f.read().strip()
            
            # Check if this is a valid URL and not our placeholder
            if download_url == "PENDING_NEW_RECORDING":
                print("Still waiting for new recording...")
                return JsonResponse({"download_url": None})
                
            # Get the timestamp when this file was last modified
            file_modification_time = os.path.getmtime(recording_file_path)
            
            # Get the timestamp when this call session started
            session_start_time = request.session.get('call_timestamp', 0)
            
            print(f"File modified at: {file_modification_time}, Call started at: {session_start_time}")
            
            # Only return the URL if the file was modified after the session started
            if file_modification_time >= session_start_time:
                print(f"✅ Found NEW download URL: {download_url}")
                return JsonResponse({"download_url": download_url})
            else:
                print("⚠️ Found old recording file - not for current call")
                return JsonResponse({"download_url": None})
            
        except Exception as e:
            print(f"❌ Error reading recording file: {e}")
            return JsonResponse({"error": str(e)})
    
    # For initial page load - don't pass any download_url
    # This forces the page to always poll for the new recording
    return render(request, 'success.html', {'download_url': ''})

# def success(request):
#     download_url= request.GET.get('download_url')
#     print(f"Redirecting sucess.html page URL: {download_url}")
#     return render(request, 'success.html',{'download_url': download_url})
=======
            # Generate the public download URL
            public_download_url = request.build_absolute_uri(f"{NGROK_URL}/media/{filename}")
            print(f"🔗 Public Download URL: {public_download_url}")
            # return JsonResponse({"download_url": public_download_url})
            if request.method == "POST":
                response = JsonResponse({"success": True, "download_url": public_download_url})
                print(f"📡 Response sent: {response.content.decode()}")  # Debugging
                return response
                
            # If it's a POST request, redirect to the GET endpoint
            return redirect(f"{NGROK_URL}/handle-recording/?RecordingSid={recording_sid}")

        print(f"⏳ Attempt {attempt + 1}: Recording not ready yet. Retrying in {retry_delay} seconds...")
        time.sleep(retry_delay)

    # If the recording is still not ready after max retries, return an error response
    print("❌ Error: Recording was not available after multiple retries.")
    return JsonResponse({"success": False, "error": "Recording not available yet."})


def success(request):
    download_url= request.GET.get('download_url')
    print(f"Redirecting sucess.html page URL: {download_url}")
    return render(request, 'success.html',{'download_url': download_url})
>>>>>>> ddc1e350f5725ad3502cddb0f3dc413050b7440d

def signup_view(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            print(f"User {user.username} created successfully!")  # ✅ Debug message
            login(request, user)
            messages.success(request, "Signup successful! Please log in.")
            return redirect('login')  # Redirect to login page
        else:
            print("Form errors:", form.errors)  # ✅ Debug errors
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

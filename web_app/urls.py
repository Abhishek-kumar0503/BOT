# web_app/urls.py
from django.urls import path
from . import views
from .views import signup_view, login_view, logout_view


urlpatterns = [
    path('', views.call_request, name='call_request'),
    path('success/', views.success, name='success'),
    path('voice/', views.voice, name='voice'),
    path('handle-recording/', views.handle_recording, name='handle_recording'),
    path('output.mp3', views.serve_mp3, name='serve_mp3'),  # Serve MP3 file
    # path('check-recording/', views.check_recording, name='check_recording'),
    path('signup/', signup_view, name='signup'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
]

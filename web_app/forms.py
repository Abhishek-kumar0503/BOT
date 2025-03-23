from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import CallRequest  # Ensure CallRequest model is correctly imported

# ✅ CallRequest Form
class CallRequestForm(forms.ModelForm):
    class Meta:
        model = CallRequest
        fields = ['phone_number', 'message']

# ✅ Signup Form (Using UserCreationForm for better password validation)
class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']  # Uses password1 & password2

# ✅ Login Form (Using Django's AuthenticationForm)
class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Username")
    password = forms.CharField(widget=forms.PasswordInput, label="Password")

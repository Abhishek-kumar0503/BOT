from django.contrib import admin
from .models import CallRequest

admin.site.register(CallRequest)

from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from .models import Profile

# admin.site.register(CallRequest)  # Register CallRequest model
admin.site.register(Profile)  # Register Profile model
admin.site.unregister(User)
admin.site.register(User, UserAdmin)  # Ensure User model is available in admin

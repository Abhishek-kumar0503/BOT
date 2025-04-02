# # web_app/models.py
# from django.db import models

# class CallRequest(models.Model):
#     phone_number = models.CharField(max_length=15)
#     message = models.TextField()
#     created_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"CallRequest {self.id}"
    


from django.contrib.auth.models import User
from django.db import models

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=100)

    def __str__(self):
        return self.user.username

class CallRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    phone_number = models.CharField(max_length=15)
    message = models.TextField()
    recording_url = models.URLField(max_length=500, blank=True, null=True)
    transcription = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Call to {self.phone_number}"   

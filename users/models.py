from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from hospital.storage_backends import MediaStorage

ROLE_CHOICES = (
    ('PATIENT', 'Patient'),
    ('DOCTOR', 'Doctor'),
    ('NURSE', 'Nurse'),
    ('LAB', 'LabScientist'),
    ('ADMIN', 'Admin'),
)

GENDER_CHOICES = (
    ('M', 'Male'),
    ('F', 'Female'),
    ('O', 'Other'),
)

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    fullname = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    profile_pix = models.ImageField(upload_to='profile/',storage=MediaStorage(), blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='PATIENT')

    def __str__(self):
        return f"{self.fullname} ({self.role})"


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        # If you want an empty profile created automatically when a User is created:
        Profile.objects.create(user=instance, fullname=instance.get_full_name() or instance.username)
    else:
        try:
            instance.profile.save()
        except Profile.DoesNotExist:
            Profile.objects.create(user=instance, fullname=instance.username)

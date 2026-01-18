# users/serializers.py - COMPLETE FIXED VERSION
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Profile, GENDER_CHOICES, ROLE_CHOICES
from django.contrib.auth.password_validation import validate_password
from .utils import SendMail
import logging

logger = logging.getLogger(__name__)

# ============================================
# UTILITY FUNCTION FOR ABSOLUTE IMAGE URL - SIMPLIFIED FIX
# ============================================
def get_absolute_profile_image_url(profile_pix):
    """Get absolute URL for profile image"""
    if not profile_pix:
        return None
    
    try:
        # ALWAYS use the .url property for FileField
        # This will give us the correct S3 URL when using S3 storage
        if hasattr(profile_pix, 'url'):
            url = profile_pix.url
            logger.info(f"📸 Generated URL via .url: {url}")
            
            # Ensure HTTPS for S3 URLs
            if 's3.amazonaws.com' in url and url.startswith('http://'):
                url = url.replace('http://', 'https://')
            
            return url
        
        # Fallback: construct URL manually
        from django.conf import settings
        if hasattr(settings, 'AWS_S3_CUSTOM_DOMAIN') and settings.AWS_S3_CUSTOM_DOMAIN:
            # S3 storage
            return f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/media/{profile_pix.name}"
        else:
            # Local storage
            base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
            return f"{base_url}/media/{profile_pix.name}"
            
    except Exception as e:
        logger.error(f"❌ Error getting URL for {profile_pix.name if profile_pix else 'None'}: {e}")
        return None

# ============================================
# USER SERIALIZER
# ============================================
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']

# ============================================
# PROFILE SERIALIZER - UPDATED TO HANDLE EMPTY FIELDS
# ============================================
class ProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    profile_pix = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = ['user', 'fullname', 'phone', 'gender', 'profile_pix', 'role']

    def get_profile_pix(self, obj):
        """Get absolute URL for profile image with robust error handling"""
        try:
            # Check if profile_pix exists and has a non-empty name
            if not obj.profile_pix or str(obj.profile_pix) == '':
                logger.debug(f"📸 {obj.user.username}: No profile image or empty field")
                return None
            
            # Get the image name
            image_name = obj.profile_pix.name
            
            # Check if it's a valid filename (not empty)
            if not image_name or image_name.strip() == '':
                logger.debug(f"📸 {obj.user.username}: Empty image name")
                return None
            
            logger.info(f"📸 {obj.user.username}: Processing image '{image_name}'")
            
            # Try to get URL via .url property
            if hasattr(obj.profile_pix, 'url'):
                try:
                    url = obj.profile_pix.url
                    logger.info(f"📸 {obj.user.username}: URL from .url: {url}")
                    
                    # Ensure HTTPS for S3 URLs
                    if url and 's3.amazonaws.com' in url and url.startswith('http://'):
                        url = url.replace('http://', 'https://')
                        logger.info(f"🔒 Forced HTTPS: {url}")
                    
                    return url
                except ValueError as e:
                    if "has no file associated with it" in str(e):
                        logger.warning(f"📸 {obj.user.username}: Image field has no file")
                        return None
                    raise
            
            # Fallback: construct URL manually for S3
            from django.conf import settings
            if hasattr(settings, 'AWS_S3_CUSTOM_DOMAIN'):
                s3_url = f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/media/{image_name}"
                logger.info(f"📸 {obj.user.username}: Constructed S3 URL: {s3_url}")
                return s3_url
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting profile_pix for {obj.user.username}: {e}", exc_info=True)
            return None
        
        

# ============================================
# REGISTRATION SERIALIZER (FIXED!)
# ============================================
class RegistrationSerializer(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.EmailField()
    password1 = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)
    fullname = serializers.CharField()
    phone = serializers.CharField(required=False, allow_blank=True)
    gender = serializers.ChoiceField(
        choices=GENDER_CHOICES,
        required=False
    )
    role = serializers.ChoiceField(
        choices=ROLE_CHOICES,
        default='PATIENT'
    )
    profile_pix = serializers.ImageField(required=False, allow_null=True)

    def validate(self, data):
        if data['password1'] != data['password2']:
            raise serializers.ValidationError("Passwords do not match.")
        
        validate_password(data['password1'])
        
        if User.objects.filter(username=data['username']).exists():
            raise serializers.ValidationError("Username already taken.")
        
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError("Email already registered.")
        
        return data

    def create(self, validated_data):
        username = validated_data.pop('username')
        email = validated_data.pop('email')
        password = validated_data.pop('password1')
        validated_data.pop('password2', None)
        profile_pix = validated_data.pop('profile_pix', None)

        # Create the user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        # Get or create profile
        profile, created = Profile.objects.get_or_create(user=user)
        
        # Update profile fields
        profile.fullname = validated_data.get('fullname', '')
        profile.phone = validated_data.get('phone', '')
        profile.gender = validated_data.get('gender', None)
        profile.role = validated_data.get('role', 'PATIENT')

        # In RegistrationSerializer.create() method - UPDATE THIS PART:
        if profile_pix:
            # Generate a clean filename
            import os
            from django.utils.text import slugify
            
            # Get file extension
            ext = os.path.splitext(profile_pix.name)[1]
            # Create a clean filename
            clean_username = slugify(username)
            filename = f"{clean_username}_profile{ext}"
            
            # DEBUG: Log file info
            logger.info(f"📸 Uploading profile image for {username}:")
            logger.info(f"   Original name: {profile_pix.name}")
            logger.info(f"   Target name: {filename}")
            logger.info(f"   Size: {profile_pix.size} bytes")
            logger.info(f"   Content type: {profile_pix.content_type}")
            
            # Save the image - force S3 upload
            try:
                # Save with the storage backend
                profile.profile_pix.save(filename, profile_pix, save=True)
                
                # Force a save to ensure database is updated
                profile.save()
                
                # Verify the upload
                if hasattr(profile.profile_pix, 'storage'):
                    try:
                        # Check if file exists in storage
                        exists = profile.profile_pix.storage.exists(profile.profile_pix.name)
                        logger.info(f"✅ Profile image upload verified: {exists}")
                        logger.info(f"✅ Image URL: {profile.profile_pix.url}")
                    except Exception as e:
                        logger.error(f"❌ Could not verify upload: {e}")
                
                logger.info(f"✅ Profile image saved for {username}: {filename}")
                
            except Exception as e:
                logger.error(f"❌ Failed to save profile image for {username}: {e}")
                # Save profile without image
                profile.save()
        else:
            profile.save()
            logger.info(f"Profile created without image for {username}")

        # Send welcome email (non-blocking)
        try:
            import threading
            def send_email_async():
                try:
                    from .utils import SendMail
                    SendMail(email)
                except Exception as e:
                    logger.warning(f"Failed to send email to {email}: {e}")
            
            email_thread = threading.Thread(target=send_email_async)
            email_thread.daemon = True
            email_thread.start()
            
            logger.info(f"User {username} registered successfully")
            
        except Exception as e:
            logger.warning(f"Failed to schedule email for {email}: {str(e)}")

        return profile

# ============================================
# UPDATE PROFILE SERIALIZER
# ============================================
class UpdateProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', required=False)
    email = serializers.EmailField(source='user.email', required=False)

    class Meta:
        model = Profile
        fields = ['username', 'email', 'fullname', 'phone', 'gender', 'profile_pix', 'role']

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        user = instance.user
        
        if 'username' in user_data:
            user.username = user_data['username']
        if 'email' in user_data:
            user.email = user_data['email']
        user.save()

        for attr in ('fullname', 'phone', 'gender', 'profile_pix', 'role'):
            if attr in validated_data:
                setattr(instance, attr, validated_data[attr])
        
        instance.save()
        return instance
# api/early_init.py
"""
Must be imported BEFORE any other Django imports.
Patches default_storage to use correct class.
"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings')

# Patch BEFORE importing django
import django.core.files.storage as storage_module

# Store original for safety
_original_default_storage = None

def patch_default_storage():
    """Patch default_storage to use correct storage class"""
    global _original_default_storage
    
    # Store original
    _original_default_storage = storage_module.default_storage
    
    # Import settings to check condition
    import django
    django.setup()
    
    from django.conf import settings
    from decouple import config
    
    # Check AWS condition manually (same as settings.py)
    AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID', default='')
    AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY', default='')
    AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME', default='etha-hospital')
    
    if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY and AWS_STORAGE_BUCKET_NAME:
        # Use MediaStorage
        from hospital.storage_backends import MediaStorage
        storage_module.default_storage = MediaStorage()
        print(f"[EARLY INIT] Patched default_storage to: MediaStorage")
    else:
        print(f"[EARLY INIT] Using original: {storage_module.default_storage.__class__.__name__}")

# Apply patch immediately
patch_default_storage()
# hospital/storage_backends.py - ENHANCED VERSION
from storages.backends.s3boto3 import S3Boto3Storage
from django.conf import settings
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# hospital/storage_backends.py - UPDATE logger statements

class MediaStorage(S3Boto3Storage):
    location = 'media'
    file_overwrite = False
    default_acl = 'public-read'
    
    def __init__(self, *args, **kwargs):
        # Force HTTPS and correct domain
        self.custom_domain = settings.AWS_S3_CUSTOM_DOMAIN
        self.secure_urls = True
        
        # Call parent init
        super().__init__(*args, **kwargs)
        
        logger.info(f"SUCCESS - MediaStorage initialized for bucket: {self.bucket_name}")  # Changed ✅ to SUCCESS
    
    # ... rest of the code ...
    
    def _verify_upload(self, name):
        """Verify that file was actually uploaded to S3"""
        try:
            # Check if file exists in S3
            self.connection.meta.client.head_object(
                Bucket=self.bucket_name,
                Key=self.location + '/' + name if self.location else name
            )
            logger.info(f"SUCCESS - Verified upload: {name} exists in S3")  # Changed ✅ to SUCCESS
            
            # Make sure it's publicly accessible
            self.connection.meta.client.put_object_acl(
                Bucket=self.bucket_name,
                Key=self.location + '/' + name if self.location else name,
                ACL='public-read'
            )
            logger.info(f"SUCCESS - Set public-read ACL for: {name}")  # Changed ✅ to SUCCESS
            
        except ClientError as e:
            logger.error(f"ERROR - Verification failed for {name}: {e}")  # Changed ❌ to ERROR
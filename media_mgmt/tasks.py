# media_mgmt/tasks.py (or a custom management command)
import os
from django.utils import timezone
from .models import PhotoDetail


def purge_expired_photos():
    """
    Identifies inactive photos whose 3-month retention has elapsed,
    deletes the file binary from the file system, and clears the path.
    """
    now = timezone.now()
    expired_photos = PhotoDetail.objects.filter(active_flag=False, purge_after__lte=now)

    for photo in expired_photos:
        if photo.image_file:
            file_path = photo.image_file.path
            if os.path.exists(file_path):
                os.remove(file_path)  # Permanently purge binary from disk
        
        # Preserve metadata and record purge status
        photo.image_file = ""
        photo.save(update_fields=['image_file'])
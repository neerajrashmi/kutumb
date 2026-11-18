import os
from django.core.management.base import BaseCommand
from django.utils import timezone
from media_mgmt.models import PhotoDetail


class Command(BaseCommand):
    help = "Purges inactive photo binary files whose 90-day retention has expired (SRS Section 17 & 33)."

    def handle(self, *args, **options):
        now = timezone.now()
        expired_photos = PhotoDetail.objects.filter(
            active_flag=False,
            purge_after__lte=now
        ).exclude(image_file='')

        purged_count = 0
        for photo in expired_photos:
            file_path = photo.image_file.path if photo.image_file else None
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                self.stdout.write(f"Purged file: {file_path}")

            # Clear path reference while preserving the DB metadata and audit record
            photo.image_file = ''
            photo.save(update_fields=['image_file', 'modified_on'])
            purged_count += 1

        self.stdout.write(self.style.SUCCESS(f"Purge complete. Successfully removed {purged_count} expired photo binaries."))
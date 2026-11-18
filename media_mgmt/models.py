import os
from django.db import models, transaction
from django.core.exceptions import ValidationError
from common.models import TimeStampedModel, DateDetail, LocationDetail, IdSequence
from genealogy.models import IndividualDetail, MarriageDetail


def photo_upload_destination(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    if instance.individual_id:
        return f"photos/individuals/{instance.individual_id}/{instance.photo_id}{ext}"
    return f"photos/marriages/{instance.marriage_id}/{instance.photo_id}{ext}"

class OccasionDetail(TimeStampedModel):
    occasion_id = models.BigAutoField(primary_key=True)
    occasion_name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    date = models.ForeignKey(DateDetail, on_delete=models.SET_NULL, null=True, blank=True)
    location = models.ForeignKey(LocationDetail, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = 'Occasion_Detail'

    def __str__(self):
        return self.occasion_name


class PhotoDetail(TimeStampedModel):
    photo_id = models.CharField(max_length=8, primary_key=True, editable=False)
    image_file = models.ImageField(upload_to=photo_upload_destination, max_length=500)
    
    # Compulsory XOR Association: Must belong to either Individual OR Marriage
    individual = models.ForeignKey(IndividualDetail, related_name='photos', on_delete=models.CASCADE, null=True, blank=True)
    marriage = models.ForeignKey(MarriageDetail, related_name='photos', on_delete=models.CASCADE, null=True, blank=True)
    
    # Occasion linkage
    occasion = models.ForeignKey(OccasionDetail, related_name='photos', on_delete=models.SET_NULL, null=True, blank=True)

    caption = models.CharField(max_length=500, blank=True, default='')
    description = models.TextField(blank=True, default='')
    owner_uploader_id = models.CharField(max_length=8)
    
    # Profile Photo Flag: Only 1 active allowed per Individual
    is_profile_photo = models.BooleanField(default=False)

    mime_type = models.CharField(max_length=100)
    file_size_bytes = models.BigIntegerField()
    width_pixels = models.IntegerField(null=True, blank=True)
    height_pixels = models.IntegerField(null=True, blank=True)

    active_flag = models.BooleanField(default=True)
    deleted_on = models.DateTimeField(null=True, blank=True)
    purge_after = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'Photo_Detail'

    def clean(self):
        # Enforce compulsory linkage to Individual XOR Marriage
        if bool(self.individual) == bool(self.marriage):
            raise ValidationError("A photo must be linked to either an Individual OR a Marriage, but not both.")

        if self.is_profile_photo and not self.individual:
            raise ValidationError("Only photos linked to an Individual can be marked as a Profile Photo.")

        # Quota checks when active
        if self.active_flag:
            if self.individual:
                count = PhotoDetail.objects.filter(individual=self.individual, active_flag=True).exclude(pk=self.pk).count()
                if count >= 15:
                    raise ValidationError("Maximum limit of 15 active photos reached for this Individual.")
            elif self.marriage:
                count = PhotoDetail.objects.filter(marriage=self.marriage, active_flag=True).exclude(pk=self.pk).count()
                if count >= 10:
                    raise ValidationError("Maximum limit of 10 active photos reached for this Marriage.")

            if self.occasion and self.individual:
                occ_count = PhotoDetail.objects.filter(individual=self.individual, occasion=self.occasion, active_flag=True).exclude(pk=self.pk).count()
                if occ_count >= 2:
                    raise ValidationError("Maximum limit of 2 active photos per Occasion reached for this Individual.")

    @transaction.atomic
    def save(self, *args, **kwargs):
        if not self.photo_id:
            self.photo_id = IdSequence.get_next_id(prefix='P', seq_type='PHOTO')
            
        self.clean()

        # If this is marked as profile photo and active, unset any previous active profile photo
        if self.is_profile_photo and self.active_flag and self.individual:
            PhotoDetail.objects.filter(
                individual=self.individual,
                is_profile_photo=True,
                active_flag=True
            ).exclude(pk=self.photo_id).update(is_profile_photo=False)

        super().save(*args, **kwargs)



class PhotoIndividualTag(TimeStampedModel):
    TAG_STATUSES = [
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    photo_tag_id = models.BigAutoField(primary_key=True)
    photo = models.ForeignKey(PhotoDetail, related_name='tags', on_delete=models.CASCADE)
    individual = models.ForeignKey(IndividualDetail, related_name='tagged_photos', on_delete=models.CASCADE)
    tagged_by_user_id = models.CharField(max_length=8)
    tag_status = models.CharField(max_length=20, choices=TAG_STATUSES, default='PENDING_APPROVAL')
    approved_by_user_id = models.CharField(max_length=8, null=True, blank=True)
    approved_on = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'Photo_Individual_Tag'
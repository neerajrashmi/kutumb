import os
from django import forms
from django.core.exceptions import ValidationError
from PIL import Image

try:
    from common.models import DateDetail, LocationDetail
    from genealogy.models import IndividualDetail, MarriageDetail
    from media_mgmt.models import PhotoDetail, OccasionDetail, PhotoIndividualTag
except ImportError:
    from common.models import DateDetail, LocationDetail
    from genealogy.models import IndividualDetail, MarriageDetail
    from media_mgmt.models import PhotoDetail, OccasionDetail, PhotoIndividualTag


ALLOWED_IMAGE_MIMES = {
    'image/jpeg': ['.jpg', '.jpeg'],
    'image/png': ['.png'],
    'image/webp': ['.webp'],
}


class PhotoUploadForm(forms.ModelForm):
    """
    Handles file upload, live camera binary capture, metadata inspection,
    and quota enforcement (SRS Sections 15 & 16).
    """
    camera_data = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = PhotoDetail
        fields = [
            'image_file',
            'individual',
            'marriage',
            'occasion',
            'caption',
            'description',
        ]
        widgets = {
            'image_file': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/jpeg,image/png,image/webp'}),
            'individual': forms.Select(attrs={'class': 'form-select'}),
            'marriage': forms.Select(attrs={'class': 'form-select'}),
            'occasion': forms.Select(attrs={'class': 'form-select'}),
            'caption': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional brief caption'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Detailed background'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        image_file = cleaned_data.get('image_file')
        camera_data = cleaned_data.get('camera_data')
        ind = cleaned_data.get('individual')
        mar = cleaned_data.get('marriage')
        occ = cleaned_data.get('occasion')

        if not image_file and not camera_data:
            raise ValidationError("Please provide a photo either via file selection or camera capture.")

        if bool(ind) == bool(mar):
            raise ValidationError("A photo must be linked to either an Individual OR a Marriage, but not both.")

        if ind:
            active_count = PhotoDetail.objects.filter(individual=ind, active_flag=True).count()
            if active_count >= 15:
                raise ValidationError(f"Individual {ind.individual_id} has reached the maximum quota of 15 active photos.")
        elif mar:
            active_count = PhotoDetail.objects.filter(marriage=mar, active_flag=True).count()
            if active_count >= 10:
                raise ValidationError(f"Marriage {mar.marriage_id} has reached the maximum quota of 10 active photos.")

        if occ and ind:
            occ_count = PhotoDetail.objects.filter(individual=ind, occasion=occ, active_flag=True).count()
            if occ_count >= 2:
                raise ValidationError("Maximum limit of 2 active photos per Occasion reached for this Individual.")

        if image_file:
            try:
                img = Image.open(image_file)
                img.verify()
                img_format = img.format.lower()
                
                format_mime_map = {'jpeg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp'}
                if img_format not in format_mime_map:
                    raise ValidationError("Unsupported file format. Please upload JPEG, PNG, or WebP.")
            except Exception:
                raise ValidationError("Uploaded file is corrupted or not a valid image.")

        return cleaned_data


class PhotoTagForm(forms.ModelForm):
    """
    Submits an individual tag for a photo (SRS Section 19).
    """
    class Meta:
        model = PhotoIndividualTag
        fields = ['individual']
        widgets = {
            'individual': forms.Select(attrs={'class': 'form-select'}),
        }
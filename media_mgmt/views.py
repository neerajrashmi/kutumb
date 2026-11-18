# apps/media_mgmt/views.py
import base64
import os
from io import BytesIO
from PIL import Image

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponseForbidden

from .models import PhotoDetail, PhotoIndividualTag
from .forms import PhotoUploadForm, PhotoTagForm
from genealogy.models import IndividualDetail


@login_required
def photo_upload_view(request):
    """
    Handles file upload & live camera frame submission.
    Extracts binary metadata and assigns P0000001 format ID automatically.
    """
    uploader_id = str(request.user.pk)

    if request.method == 'POST':
        form = PhotoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            photo_instance = form.save(commit=False)
            photo_instance.owner_uploader_id = uploader_id

            camera_data = form.cleaned_data.get('camera_data')

            # Handle camera capture base64 payload if camera was used
            if camera_data and not request.FILES.get('image_file'):
                header, encoded = camera_data.split(';base64,')
                file_data = base64.b64decode(encoded)
                file_stream = BytesIO(file_data)
                
                img = Image.open(file_stream)
                width, height = img.size
                mime_type = 'image/jpeg'
                ext = '.jpg'

                filename = f"capture_{timezone.now().strftime('%Y%m%d_%H%M%S')}{ext}"
                photo_instance.image_file.save(filename, ContentFile(file_data), save=False)
                photo_instance.mime_type = mime_type
                photo_instance.file_size_bytes = len(file_data)
                photo_instance.width_pixels = width
                photo_instance.height_pixels = height
            else:
                # Normal file upload: inspect uploaded binary
                uploaded = request.FILES['image_file']
                img = Image.open(uploaded)
                photo_instance.width_pixels, photo_instance.height_pixels = img.size
                photo_instance.file_size_bytes = uploaded.size
                photo_instance.mime_type = getattr(uploaded, 'content_type', Image.MIME.get(img.format, 'image/jpeg'))

            photo_instance.save()

            # SRS 19: If uploader tags themselves, auto-approve
            if photo_instance.individual and photo_instance.individual.individual_id == uploader_id:
                PhotoIndividualTag.objects.create(
                    photo=photo_instance,
                    individual=photo_instance.individual,
                    tagged_by_user_id=uploader_id,
                    tag_status='APPROVED',
                    approved_by_user_id=uploader_id,
                    approved_on=timezone.now()
                )

            messages.success(request, f"Photo {photo_instance.photo_id} successfully saved.")
            return redirect('media_mgmt:photo_detail', photo_id=photo_instance.photo_id)
    else:
        # Prepopulate individual if passed in query string (?individual_id=I0000001)
        initial = {}
        target_ind = request.GET.get('individual_id')
        if target_ind:
            initial['individual'] = target_ind
        form = PhotoUploadForm(initial=initial)

    return render(request, 'media_mgmt/photo_upload.html', {
        'form': form,
        'title': 'Upload Photo / Capture from Camera'
    })


@login_required
def photo_detail_view(request, photo_id):
    """
    Renders photo viewer, metadata details, and tag list with approval buttons.
    """
    photo = get_object_or_404(PhotoDetail, pk=photo_id)
    tags = photo.tags.select_related('individual').all()
    current_user_id = str(request.user.pk)

    is_owner = (photo.owner_uploader_id == current_user_id)

    tag_form = PhotoTagForm()
    if request.method == 'POST' and 'submit_tag' in request.POST:
        tag_form = PhotoTagForm(request.POST)
        if tag_form.is_valid():
            tag = tag_form.save(commit=False)
            tag.photo = photo
            tag.tagged_by_user_id = current_user_id
            
            # Owner tags are auto-approved; others require owner action (SRS Section 19)
            if is_owner:
                tag.tag_status = 'APPROVED'
                tag.approved_by_user_id = current_user_id
                tag.approved_on = timezone.now()
            else:
                tag.tag_status = 'PENDING_APPROVAL'

            try:
                tag.save()
                messages.success(request, "Tag added.")
            except Exception:
                messages.error(request, "This individual is already tagged in this photo.")
            return redirect('media_mgmt:photo_detail', photo_id=photo.photo_id)

    return render(request, 'media_mgmt/photo_detail.html', {
        'photo': photo,
        'tags': tags,
        'is_owner': is_owner,
        'tag_form': tag_form,
    })


@login_required
def photo_tag_action_view(request, photo_tag_id, action):
    """
    Approves or rejects tag suggestions (SRS Section 19).
    """
    tag = get_object_or_404(PhotoIndividualTag, pk=photo_tag_id)
    current_user_id = str(request.user.pk)

    if tag.photo.owner_uploader_id != current_user_id:
        return HttpResponseForbidden("Only the photo owner may approve or reject tags.")

    if action == 'approve':
        tag.tag_status = 'APPROVED'
        tag.approved_by_user_id = current_user_id
        tag.approved_on = timezone.now()
        tag.save()
        messages.success(request, f"Tag approved for {tag.individual}.")
    elif action == 'reject':
        tag.tag_status = 'REJECTED'
        tag.save()
        messages.warning(request, f"Tag rejected for {tag.individual}.")

    return redirect('media_mgmt:photo_detail', photo_id=tag.photo.photo_id)


@login_required
def photo_gallery_view(request, individual_id=None):
    """
    Displays active gallery photos associated with an individual or all photos.
    """
    if individual_id:
        person = get_object_or_404(IndividualDetail, pk=individual_id)
        photos = PhotoDetail.objects.filter(
            individual=person, active_flag=True
        ).order_by('-created_on')
    else:
        person = None
        photos = PhotoDetail.objects.filter(active_flag=True).order_by('-created_on')

    return render(request, 'media_mgmt/photo_gallery.html', {
        'person': person,
        'photos': photos,
    })
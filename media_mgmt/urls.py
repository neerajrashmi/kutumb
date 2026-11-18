# apps/media_mgmt/urls.py
from django.urls import path
from . import views

app_name = 'media_mgmt'

urlpatterns = [
    # Photo Upload Routes (aliases to support both reverse lookups)
    path('upload/', views.photo_upload_view, name='photo_upload'),
    path('upload-photo/', views.photo_upload_view, name='upload_photo'),

    # Photo Viewing & Detail
    path('view/<str:photo_id>/', views.photo_detail_view, name='photo_detail'),

    # Photo Tagging Workflow Actions (Approve / Reject)
    path('tag/<int:photo_tag_id>/<str:action>/', views.photo_tag_action_view, name='photo_tag_action'),

    # Gallery View (Individual-scoped and all photos)
    path('gallery/', views.photo_gallery_view, name='photo_gallery'),
    path('gallery/<str:individual_id>/', views.photo_gallery_view, name='individual_photo_gallery'),
]
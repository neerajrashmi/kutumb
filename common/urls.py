from django.urls import path
from . import views

app_name = 'common'

urlpatterns = [
    path('locations/<int:location_id>/geocode/', views.geocode_location_view, name='location_geocode'),
]
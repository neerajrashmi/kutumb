# apps/contacts/urls.py
from django.urls import path
from . import views

app_name = 'contacts'

urlpatterns = [
    # Main Contact Hub (supports both /contacts/individual/<id>/ and /contacts/manage/<id>/)
    path('individual/<str:individual_id>/', views.individual_contacts_manage_view, name='manage_contacts'),
    path('manage/<str:individual_id>/', views.individual_contacts_manage_view, name='manage_contacts_alias'),

    # Physical Address routes
    path('individual/<str:individual_id>/address/add/', views.add_physical_address, name='add_address'),
    path('address/<int:address_id>/edit/', views.edit_address_view, name='edit_address'),
    path('address/<int:address_id>/make-primary/', views.toggle_address_primary_view, name='make_primary_address'),

    # Phone Number routes
    path('individual/<str:individual_id>/phone/add/', views.add_phone, name='add_phone'),
    path('phone/<int:phone_id>/edit/', views.edit_phone_view, name='edit_phone'),
    path('phone/<int:phone_id>/toggle/', views.toggle_phone_status_view, name='toggle_phone'),

    # Email Address routes
    path('individual/<str:individual_id>/email/add/', views.add_email, name='add_email'),
    path('email/<int:email_id>/edit/', views.edit_email_view, name='edit_email'),
    path('email/<int:email_id>/toggle/', views.toggle_email_status_view, name='toggle_email'),
]
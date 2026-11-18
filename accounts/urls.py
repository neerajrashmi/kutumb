# apps/accounts/urls.py
from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),    
    path('access/', views.access_dashboard_view, name='access_dashboard'),
    path('access/<int:access_id>/revoke/', views.revoke_access_view, name='revoke_access'),
    path('invite/', views.invite_member_view, name='invite_member'),
    path('register/invite/<str:token>/', views.register_invited_user_view, name='register_invited_user'),
]
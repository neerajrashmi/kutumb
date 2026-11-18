"""
apps/genealogy/urls.py
Routing definitions for Tree Visualizer and Contextual Member Management.
"""
from django.urls import path
from . import views

app_name = 'genealogy'

urlpatterns = [
    path('dashboard/', views.executive_dashboard_view, name='dashboard'),
    path('tree/', views.tree_view, name='my_tree'),
    path('tree/<str:individual_id>/', views.tree_view, name='individual_tree'),
    path('api/tree-data/<str:individual_id>/', views.tree_data_api, name='api_tree_data'),
    path('api/search-members/', views.individual_search_api, name='api_search_members'),
    
    # Member lifecycle (Contextually linked to family nodes)
    path('individual/add/', views.individual_create_view, name='individual_add'),
    path('individual/<str:individual_id>/edit/', views.individual_edit_view, name='individual_edit'),
]
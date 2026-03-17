from django.urls import path

from .views import lims_dashboard_summary, lims_permissions_summary

app_name = 'lims'


urlpatterns = [
    path('permissions', lims_permissions_summary, name='permissions'),
    path('summary', lims_dashboard_summary, name='summary'),
]

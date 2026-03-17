from django.urls import path

from .views import lims_dashboard_summary

app_name = 'lims'


urlpatterns = [
    path('summary', lims_dashboard_summary, name='summary'),
]

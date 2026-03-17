from django.urls import path

from .views import (
    lims_dashboard_summary,
    lims_permissions_summary,
    lims_reference_address_sync_runs,
    lims_reference_lab_detail,
    lims_reference_labs,
    lims_reference_select_options,
    lims_reference_site_detail,
    lims_reference_sites,
    lims_reference_studies,
    lims_reference_study_detail,
)

app_name = 'lims'


urlpatterns = [
    path("reference/address-sync-runs", lims_reference_address_sync_runs, name="reference_address_sync_runs"),
    path("reference/labs", lims_reference_labs, name="reference_labs"),
    path("reference/labs/<uuid:lab_id>", lims_reference_lab_detail, name="reference_lab_detail"),
    path("reference/select-options", lims_reference_select_options, name="reference_select_options"),
    path("reference/sites", lims_reference_sites, name="reference_sites"),
    path("reference/sites/<uuid:site_id>", lims_reference_site_detail, name="reference_site_detail"),
    path("reference/studies", lims_reference_studies, name="reference_studies"),
    path("reference/studies/<uuid:study_id>", lims_reference_study_detail, name="reference_study_detail"),
    path('permissions', lims_permissions_summary, name='permissions'),
    path('summary', lims_dashboard_summary, name='summary'),
]

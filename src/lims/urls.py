from django.urls import path

from .views import (
    lims_dashboard_summary,
    lims_metadata_field_definition_detail,
    lims_metadata_field_definitions,
    lims_metadata_schema_bindings,
    lims_metadata_schema_detail,
    lims_metadata_schema_version_publish,
    lims_metadata_schema_versions,
    lims_metadata_schemas,
    lims_metadata_validate,
    lims_metadata_vocabulary_detail,
    lims_metadata_vocabularies,
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
    path("metadata/bindings", lims_metadata_schema_bindings, name="metadata_bindings"),
    path("metadata/field-definitions", lims_metadata_field_definitions, name="metadata_field_definitions"),
    path(
        "metadata/field-definitions/<uuid:definition_id>",
        lims_metadata_field_definition_detail,
        name="metadata_field_definition_detail",
    ),
    path("metadata/schemas", lims_metadata_schemas, name="metadata_schemas"),
    path("metadata/schemas/<uuid:schema_id>", lims_metadata_schema_detail, name="metadata_schema_detail"),
    path("metadata/schemas/<uuid:schema_id>/versions", lims_metadata_schema_versions, name="metadata_schema_versions"),
    path(
        "metadata/schemas/<uuid:schema_id>/versions/<uuid:version_id>/publish",
        lims_metadata_schema_version_publish,
        name="metadata_schema_version_publish",
    ),
    path("metadata/validate", lims_metadata_validate, name="metadata_validate"),
    path("metadata/vocabularies", lims_metadata_vocabularies, name="metadata_vocabularies"),
    path("metadata/vocabularies/<uuid:vocabulary_id>", lims_metadata_vocabulary_detail, name="metadata_vocabulary_detail"),
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

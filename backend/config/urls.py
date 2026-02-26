"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

from core.views import (
    access_request_decision,
    access_requests,
    asset_classifications,
    asset_detail,
    asset_contracts,
    assets,
    contract_activate,
    classification_activate,
    classification_deprecate,
    classification_detail,
    classifications,
    contract_deprecate,
    contract_detail,
    contracts,
    health,
    healthz,
    ingestion_detail,
    ingestions,
    lineage_edges,
    livez,
    metrics,
    master_merge_candidate_approve,
    master_merge_candidates,
    master_record_detail,
    master_records,
    print_job_detail,
    print_job_status,
    print_jobs,
    privacy_consent_events,
    privacy_profile_detail,
    privacy_profiles,
    residency_check,
    residency_profile_activate,
    residency_profile_deprecate,
    residency_profile_detail,
    residency_profiles,
    retention_hold_release,
    retention_holds,
    retention_rules,
    retention_runs,
    quality_results,
    quality_rule_evaluate,
    quality_rules,
    reference_dataset_activate,
    reference_dataset_version_values,
    reference_dataset_versions,
    reference_datasets,
    readyz,
    search_assets,
)
from tenants.views import tenants

urlpatterns = [
    path('', health, name='health'),
    path('healthz', healthz, name='healthz'),
    path('livez', livez, name='livez'),
    path('readyz', readyz, name='readyz'),
    path('metrics', metrics, name='metrics'),
    path('api/v1/tenants', tenants, name='tenants'),
    path('api/v1/assets', assets, name='assets'),
    path('api/v1/assets/<uuid:asset_id>', asset_detail, name='asset_detail'),
    path('api/v1/assets/<uuid:asset_id>/classifications', asset_classifications, name='asset_classifications'),
    path('api/v1/classifications', classifications, name='classifications'),
    path('api/v1/classifications/<uuid:classification_id>', classification_detail, name='classification_detail'),
    path('api/v1/classifications/<uuid:classification_id>/activate', classification_activate, name='classification_activate'),
    path('api/v1/classifications/<uuid:classification_id>/deprecate', classification_deprecate, name='classification_deprecate'),
    path('api/v1/master-data/<str:entity_type>/records', master_records, name='master_records'),
    path(
        'api/v1/master-data/<str:entity_type>/records/<uuid:master_id>',
        master_record_detail,
        name='master_record_detail',
    ),
    path(
        'api/v1/master-data/<str:entity_type>/merge-candidates',
        master_merge_candidates,
        name='master_merge_candidates',
    ),
    path(
        'api/v1/master-data/<str:entity_type>/merge-candidates/<uuid:candidate_id>/approve',
        master_merge_candidate_approve,
        name='master_merge_candidate_approve',
    ),
    path('api/v1/access-requests', access_requests, name='access_requests'),
    path('api/v1/access-requests/<uuid:request_id>/decision', access_request_decision, name='access_request_decision'),
    path('api/v1/printing/jobs', print_jobs, name='print_jobs'),
    path('api/v1/printing/jobs/<uuid:job_id>', print_job_detail, name='print_job_detail'),
    path('api/v1/printing/jobs/<uuid:job_id>/status', print_job_status, name='print_job_status'),
    path('api/v1/assets/<uuid:asset_id>/contracts', asset_contracts, name='asset_contracts'),
    path('api/v1/contracts', contracts, name='contracts'),
    path('api/v1/contracts/<uuid:contract_id>', contract_detail, name='contract_detail'),
    path('api/v1/contracts/<uuid:contract_id>/activate', contract_activate, name='contract_activate'),
    path('api/v1/contracts/<uuid:contract_id>/deprecate', contract_deprecate, name='contract_deprecate'),
    path('api/v1/retention/rules', retention_rules, name='retention_rules'),
    path('api/v1/retention/holds', retention_holds, name='retention_holds'),
    path('api/v1/retention/holds/<uuid:hold_id>/release', retention_hold_release, name='retention_hold_release'),
    path('api/v1/retention/runs', retention_runs, name='retention_runs'),
    path('api/v1/privacy/profiles', privacy_profiles, name='privacy_profiles'),
    path('api/v1/privacy/profiles/<uuid:profile_id>', privacy_profile_detail, name='privacy_profile_detail'),
    path('api/v1/privacy/consent-events', privacy_consent_events, name='privacy_consent_events'),
    path('api/v1/residency/profiles', residency_profiles, name='residency_profiles'),
    path('api/v1/residency/profiles/<uuid:profile_id>', residency_profile_detail, name='residency_profile_detail'),
    path('api/v1/residency/profiles/<uuid:profile_id>/activate', residency_profile_activate, name='residency_profile_activate'),
    path('api/v1/residency/profiles/<uuid:profile_id>/deprecate', residency_profile_deprecate, name='residency_profile_deprecate'),
    path('api/v1/residency/check', residency_check, name='residency_check'),
    path('api/v1/reference-data/datasets', reference_datasets, name='reference_datasets'),
    path('api/v1/reference-data/datasets/<uuid:dataset_id>/versions', reference_dataset_versions, name='reference_dataset_versions'),
    path(
        'api/v1/reference-data/datasets/<uuid:dataset_id>/versions/<int:version>/activate',
        reference_dataset_activate,
        name='reference_dataset_activate',
    ),
    path(
        'api/v1/reference-data/datasets/<uuid:dataset_id>/versions/<int:version>/values',
        reference_dataset_version_values,
        name='reference_dataset_version_values',
    ),
    path('api/v1/quality/rules', quality_rules, name='quality_rules'),
    path('api/v1/quality/rules/<uuid:rule_id>/evaluate', quality_rule_evaluate, name='quality_rule_evaluate'),
    path('api/v1/quality/results', quality_results, name='quality_results'),
    path('api/v1/ingestions', ingestions, name='ingestions'),
    path('api/v1/ingestions/<uuid:ingestion_id>', ingestion_detail, name='ingestion_detail'),
    path('api/v1/search/assets', search_assets, name='search_assets'),
    path('api/v1/lineage/edges', lineage_edges, name='lineage_edges'),
    path('admin/', admin.site.urls),
]

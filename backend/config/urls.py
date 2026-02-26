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
    asset_detail,
    asset_contracts,
    assets,
    contract_activate,
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
    quality_results,
    quality_rule_evaluate,
    quality_rules,
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
    path('api/v1/assets/<uuid:asset_id>/contracts', asset_contracts, name='asset_contracts'),
    path('api/v1/contracts', contracts, name='contracts'),
    path('api/v1/contracts/<uuid:contract_id>', contract_detail, name='contract_detail'),
    path('api/v1/contracts/<uuid:contract_id>/activate', contract_activate, name='contract_activate'),
    path('api/v1/contracts/<uuid:contract_id>/deprecate', contract_deprecate, name='contract_deprecate'),
    path('api/v1/quality/rules', quality_rules, name='quality_rules'),
    path('api/v1/quality/rules/<uuid:rule_id>/evaluate', quality_rule_evaluate, name='quality_rule_evaluate'),
    path('api/v1/quality/results', quality_results, name='quality_results'),
    path('api/v1/ingestions', ingestions, name='ingestions'),
    path('api/v1/ingestions/<uuid:ingestion_id>', ingestion_detail, name='ingestion_detail'),
    path('api/v1/search/assets', search_assets, name='search_assets'),
    path('api/v1/lineage/edges', lineage_edges, name='lineage_edges'),
    path('admin/', admin.site.urls),
]

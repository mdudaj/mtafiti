from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Callable
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urljoin, urlsplit

from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from core.models import PrintJob, PrintTemplate
from core.printing_renderers import render_label_preview

from .models import (
    AccessioningManifest,
    AccessioningManifestItem,
    ApprovalRecord,
    BatchPlate,
    BatchPlateAssignment,
    Biospecimen,
    BiospecimenPool,
    BiospecimenPoolMember,
    BiospecimenStorageRecord,
    BiospecimenType,
    Country,
    District,
    FormPackage,
    FormPackageChoice,
    FormPackageChoiceList,
    FormPackageCompilerDiagnostic,
    FormPackageItem,
    FormPackageItemGroup,
    FormPackageProjection,
    FormPackageSection,
    FormPackageSourceArtifact,
    FormPackageVersion,
    InventoryLot,
    InventoryMaterial,
    InventoryTransaction,
    MaterialUsageRecord,
    MetadataFieldDefinition,
    MetadataSchemaBinding,
    MetadataSchemaField,
    MetadataSchemaVersion,
    MetadataVocabulary,
    MetadataVocabularyDomain,
    MetadataVocabularyItem,
    OperationDefinition,
    OperationRun,
    OperationVersion,
    PlateLayoutTemplate,
    Postcode,
    ProcessingBatch,
    QCResult,
    ReceivingDiscrepancy,
    ReceivingEvent,
    Region,
    StorageLocation,
    Street,
    SubmissionRecord,
    TanzaniaAddressSyncRun,
    TaskRun,
    Ward,
    WorkflowEdgeTemplate,
    WorkflowNodeTemplate,
    WorkflowStepBinding,
    WorkflowTemplate,
    WorkflowTemplateVersion,
)

TANZANIA_POSTCODE_ROOT_URL = "https://www.tanzaniapostcode.com/"
POSTCODE_RE = re.compile(r"\b\d{5}\b")
DEFAULT_METADATA_VOCABULARY_DOMAIN_CODE = "general"
DEFAULT_METADATA_VOCABULARY_PACK = (
    {
        "domain": {
            "code": "roles",
            "name": "Roles",
            "description": "Role and responsibility vocabularies for study, site, laboratory, and workflow assignments.",
        },
        "vocabularies": (
            {
                "code": "study-team-roles",
                "name": "Study team roles",
                "description": "Common responsibilities for study coordination and site operations.",
                "items": (
                    ("principal-investigator", "Principal investigator"),
                    ("study-coordinator", "Study coordinator"),
                    ("site-coordinator", "Site coordinator"),
                    ("laboratory-technician", "Laboratory technician"),
                    ("data-manager", "Data manager"),
                    ("qa-officer", "QA officer"),
                ),
            },
        ),
    },
    {
        "domain": {
            "code": "consent",
            "name": "Consent",
            "description": "Consent and participation state vocabularies.",
        },
        "vocabularies": (
            {
                "code": "consent-status",
                "name": "Consent status",
                "description": "Controlled values describing participant consent state.",
                "items": (
                    ("pending", "Pending"),
                    ("received", "Received"),
                    ("waived", "Waived"),
                    ("withdrawn", "Withdrawn"),
                ),
            },
        ),
    },
    {
        "domain": {
            "code": "outcomes",
            "name": "Outcomes",
            "description": "Laboratory and workflow outcome vocabularies.",
        },
        "vocabularies": (
            {
                "code": "test-outcome",
                "name": "Test outcome",
                "description": "Common qualitative outcome values for diagnostic or assay workflows.",
                "items": (
                    ("positive", "Positive"),
                    ("negative", "Negative"),
                    ("indeterminate", "Indeterminate"),
                    ("invalid", "Invalid"),
                ),
            },
        ),
    },
    {
        "domain": {
            "code": "biospecimen",
            "name": "Biospecimen",
            "description": "Condition and handling vocabularies for biospecimen operations.",
        },
        "vocabularies": (
            {
                "code": "sample-condition",
                "name": "Sample condition",
                "description": "Observed specimen condition at receipt or review.",
                "items": (
                    ("acceptable", "Acceptable"),
                    ("haemolysed", "Haemolysed"),
                    ("clotted", "Clotted"),
                    ("insufficient-volume", "Insufficient volume"),
                    ("leaking", "Leaking"),
                ),
            },
        ),
    },
    {
        "domain": {
            "code": "workflow",
            "name": "Workflow",
            "description": "Decision and transition vocabularies for workflow-driven tasks.",
        },
        "vocabularies": (
            {
                "code": "workflow-decision",
                "name": "Workflow decision",
                "description": "Common decision values used when progressing configurable workflows.",
                "items": (
                    ("accept", "Accept"),
                    ("reject", "Reject"),
                    ("repeat", "Repeat"),
                    ("escalate", "Escalate"),
                ),
            },
        ),
    },
    {
        "domain": {
            "code": "units",
            "name": "Units",
            "description": "Measurement and reporting unit vocabularies.",
        },
        "vocabularies": (
            {
                "code": "temperature-unit",
                "name": "Temperature unit",
                "description": "Temperature units for storage, transport, and reporting.",
                "items": (
                    ("celsius", "Celsius"),
                    ("fahrenheit", "Fahrenheit"),
                ),
            },
        ),
    },
)
SAMPLE_ACCESSION_REFERENCE_OPERATION_CODE = "sample-accession"
SAMPLE_ACCESSION_REFERENCE_PACKAGE_CODE = "sample-accession-package"
SAMPLE_ACCESSION_REFERENCE_SECTION_KEYS = [
    "intake",
    "qc",
    "storage",
    "rejection",
]
SAMPLE_ACCESSION_REFERENCE_SOURCE_MODES = ["single", "batch", "edc_import"]
SAMPLE_ACCESSION_REFERENCE_TASK_KEYS = {
    "intake": "intake_capture",
    "qc": "qc_decision",
    "storage": "storage_logging",
}
SAMPLE_ACCESSION_REFERENCE_TRANSITIONAL_ADAPTERS = [
    "/api/v1/lims/accessioning/receive-single",
    "/api/v1/lims/accessioning/manifests/<manifest_id>/items/" "<item_id>/receive",
]
SAMPLE_ACCESSION_REFERENCE_QC_BINDING_ITEM_KEYS = [
    "qc_decision",
    "qc_notes",
    "rejection_code",
    "reason",
]


class AddressSyncFetchError(RuntimeError):
    pass


@dataclass
class ParsedLink:
    label: str
    url: str
    path: str


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self._href = href
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._href is None:
            return
        label = " ".join("".join(self._chunks).split())
        self.links.append((self._href, label))
        self._href = None
        self._chunks = []


def fetch_html(url: str, *, timeout: int = 20) -> str:
    req = urllib_request.Request(
        url,
        headers={
            "User-Agent": "Mtafiti-LIMS-ReferenceSync/1.0 (+polite; contact tenant admin)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    try:
        with urllib_request.urlopen(req, timeout=timeout) as response:
            encoding = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(encoding, errors="replace")
    except urllib_error.HTTPError as exc:
        raise AddressSyncFetchError(f"http_error:{exc.code}") from exc
    except (urllib_error.URLError, TimeoutError, OSError) as exc:
        raise AddressSyncFetchError("transport_error") from exc


def parse_directory_links(html: str, base_url: str) -> list[ParsedLink]:
    parser = _AnchorParser()
    parser.feed(html)
    root_host = urlsplit(TANZANIA_POSTCODE_ROOT_URL).netloc
    seen: set[str] = set()
    links: list[ParsedLink] = []
    for href, label in parser.links:
        absolute = urljoin(base_url, href)
        parts = urlsplit(absolute)
        if parts.scheme not in {"http", "https"}:
            continue
        if parts.netloc != root_host:
            continue
        path = parts.path or "/"
        if path == "/" or path in seen:
            continue
        if not label or POSTCODE_RE.search(label):
            continue
        seen.add(path)
        links.append(ParsedLink(label=label, url=absolute, path=path))
    return links


def parse_postcode(html: str) -> str:
    match = POSTCODE_RE.search(html)
    return match.group(0) if match else ""


def default_sync_stats() -> dict[str, int]:
    return {
        "failure_count": 0,
        "countries_created": 0,
        "countries_updated": 0,
        "regions_created": 0,
        "regions_updated": 0,
        "districts_created": 0,
        "districts_updated": 0,
        "wards_created": 0,
        "wards_updated": 0,
        "streets_created": 0,
        "streets_updated": 0,
        "postcodes_created": 0,
        "postcodes_updated": 0,
    }


def ensure_sync_seed_queue(run: TanzaniaAddressSyncRun) -> None:
    checkpoint = dict(run.checkpoint or {})
    if checkpoint.get("queue"):
        return
    checkpoint["queue"] = [{"level": "root", "url": run.source_root}]
    checkpoint["seen_keys"] = []
    run.checkpoint = checkpoint
    if not run.stats:
        run.stats = default_sync_stats()


def _queue_items(run: TanzaniaAddressSyncRun) -> list[dict[str, str]]:
    checkpoint = dict(run.checkpoint or {})
    return list(checkpoint.get("queue") or [])


def _replace_queue(run: TanzaniaAddressSyncRun, queue: list[dict[str, str]]) -> None:
    checkpoint = dict(run.checkpoint or {})
    checkpoint["queue"] = queue
    run.checkpoint = checkpoint


def _seen_keys(run: TanzaniaAddressSyncRun) -> list[str]:
    checkpoint = dict(run.checkpoint or {})
    return list(checkpoint.get("seen_keys") or [])


def _record_seen_keys(run: TanzaniaAddressSyncRun, seen_keys: list[str]) -> None:
    checkpoint = dict(run.checkpoint or {})
    checkpoint["seen_keys"] = seen_keys
    run.checkpoint = checkpoint


def enqueue_unique(run: TanzaniaAddressSyncRun, items: list[dict[str, str]]) -> None:
    queue = _queue_items(run)
    seen_keys = _seen_keys(run)
    seen = set(seen_keys)
    for item in items:
        key = f"{item['level']}|{item['url']}"
        if key in seen:
            continue
        queue.append(item)
        seen_keys.append(key)
        seen.add(key)
    _replace_queue(run, queue)
    _record_seen_keys(run, seen_keys)


def _increment_stat(run: TanzaniaAddressSyncRun, key: str) -> None:
    stats = dict(run.stats or default_sync_stats())
    stats[key] = int(stats.get(key, 0)) + 1
    run.stats = stats


def _sync_progress_fields(run: TanzaniaAddressSyncRun) -> dict[str, object]:
    checkpoint = dict(run.checkpoint or {})
    queue_size = len(checkpoint.get("queue") or [])
    processed_count = int(run.pages_processed or 0)
    discovered_workload = processed_count + queue_size
    if run.status == TanzaniaAddressSyncRun.Status.COMPLETED:
        progress_percent = 100
    elif discovered_workload > 0:
        progress_percent = round((processed_count / discovered_workload) * 100, 1)
    else:
        progress_percent = 0
    stats = dict(run.stats or {})
    return {
        "queue_size": queue_size,
        "remaining_count": queue_size,
        "processed_count": processed_count,
        "failure_count": int(stats.get("failure_count") or 0),
        "discovered_workload": discovered_workload,
        "progress_percent": progress_percent,
    }


def _ensure_tanzania_country() -> tuple[Country, bool]:
    defaults = {
        "name": "Tanzania",
        "slug": "tanzania",
        "source_url": TANZANIA_POSTCODE_ROOT_URL,
        "is_active": True,
        "last_synced_at": timezone.now(),
    }
    country, created = Country.objects.update_or_create(code="TZ", defaults=defaults)
    return country, created


def _save_existing_sync_record(instance, values: dict[str, object]):
    for field_name, value in values.items():
        setattr(instance, field_name, value)
    instance.save(update_fields=[*values.keys(), "updated_at"])
    return instance, False


def _update_or_create_sync_record(
    model,
    *,
    lookup: dict[str, object],
    defaults: dict[str, object],
    fallbacks: list[dict[str, object]],
):
    for fallback in fallbacks:
        candidate = model.objects.filter(**fallback).first()
        if candidate is not None:
            return _save_existing_sync_record(candidate, defaults)

    candidate = model.objects.filter(**lookup).first()
    if candidate is not None:
        return _save_existing_sync_record(candidate, defaults)

    try:
        return model.objects.create(**lookup, **defaults), True
    except IntegrityError:
        for fallback in fallbacks:
            candidate = model.objects.filter(**fallback).first()
            if candidate is not None:
                return _save_existing_sync_record(candidate, defaults)
        candidate = model.objects.filter(**lookup).first()
        if candidate is not None:
            return _save_existing_sync_record(candidate, defaults)
        raise


def _upsert_region(country: Country, link: ParsedLink):
    defaults = {
        "country": country,
        "name": link.label,
        "slug": slugify(link.label),
        "source_url": link.url,
        "is_active": True,
        "last_synced_at": timezone.now(),
    }
    region, created = _update_or_create_sync_record(
        Region,
        lookup={"source_path": link.path},
        defaults=defaults,
        fallbacks=[{"country": country, "name": link.label}],
    )
    return region, created


def _upsert_district(region: Region, link: ParsedLink):
    defaults = {
        "region": region,
        "name": link.label,
        "slug": slugify(link.label),
        "source_url": link.url,
        "is_active": True,
        "last_synced_at": timezone.now(),
    }
    district, created = _update_or_create_sync_record(
        District,
        lookup={"source_path": link.path},
        defaults=defaults,
        fallbacks=[{"region": region, "name": link.label}],
    )
    return district, created


def _upsert_ward(district: District, link: ParsedLink):
    defaults = {
        "district": district,
        "name": link.label,
        "slug": slugify(link.label),
        "source_url": link.url,
        "is_active": True,
        "last_synced_at": timezone.now(),
    }
    ward, created = _update_or_create_sync_record(
        Ward,
        lookup={"source_path": link.path},
        defaults=defaults,
        fallbacks=[{"district": district, "name": link.label}],
    )
    return ward, created


def _upsert_street(ward: Ward, link: ParsedLink):
    defaults = {
        "ward": ward,
        "name": link.label,
        "slug": slugify(link.label),
        "source_url": link.url,
        "is_active": True,
        "last_synced_at": timezone.now(),
    }
    street, created = _update_or_create_sync_record(
        Street,
        lookup={"source_path": link.path},
        defaults=defaults,
        fallbacks=[{"ward": ward, "name": link.label}],
    )
    return street, created


def _upsert_postcode(street: Street, link: ParsedLink, code: str):
    defaults = {
        "street": street,
        "code": code,
        "source_url": link.url,
        "is_active": True,
        "last_synced_at": timezone.now(),
    }
    postcode, created = _update_or_create_sync_record(
        Postcode,
        lookup={"source_path": link.path},
        defaults=defaults,
        fallbacks=[{"street": street, "code": code}],
    )
    return postcode, created


def _process_item(
    run: TanzaniaAddressSyncRun,
    item: dict[str, str],
    html: str,
) -> None:
    level = item["level"]
    if level == "root":
        country, created = _ensure_tanzania_country()
        _increment_stat(run, "countries_created" if created else "countries_updated")
        region_items: list[dict[str, str]] = []
        for link in parse_directory_links(html, item["url"]):
            region, created = _upsert_region(country, link)
            _increment_stat(run, "regions_created" if created else "regions_updated")
            region_items.append(
                {
                    "level": "region",
                    "url": link.url,
                    "region_id": str(region.id),
                }
            )
        enqueue_unique(run, region_items)
        return

    if level == "region":
        region = Region.objects.get(id=item["region_id"])
        district_items: list[dict[str, str]] = []
        for link in parse_directory_links(html, item["url"]):
            district, created = _upsert_district(region, link)
            _increment_stat(
                run, "districts_created" if created else "districts_updated"
            )
            district_items.append(
                {
                    "level": "district",
                    "url": link.url,
                    "district_id": str(district.id),
                }
            )
        enqueue_unique(run, district_items)
        return

    if level == "district":
        district = District.objects.get(id=item["district_id"])
        ward_items: list[dict[str, str]] = []
        for link in parse_directory_links(html, item["url"]):
            ward, created = _upsert_ward(district, link)
            _increment_stat(run, "wards_created" if created else "wards_updated")
            ward_items.append(
                {
                    "level": "ward",
                    "url": link.url,
                    "ward_id": str(ward.id),
                }
            )
        enqueue_unique(run, ward_items)
        return

    if level == "ward":
        ward = Ward.objects.get(id=item["ward_id"])
        street_items: list[dict[str, str]] = []
        for link in parse_directory_links(html, item["url"]):
            street_items.append(
                {
                    "level": "street",
                    "url": link.url,
                    "ward_id": str(ward.id),
                    "street_label": link.label,
                    "street_path": link.path,
                }
            )
        enqueue_unique(run, street_items)
        return

    if level == "street":
        ward = Ward.objects.get(id=item["ward_id"])
        link = ParsedLink(
            label=item["street_label"],
            url=item["url"],
            path=item["street_path"],
        )
        street, created = _upsert_street(ward, link)
        _increment_stat(run, "streets_created" if created else "streets_updated")
        postcode_code = parse_postcode(html)
        if postcode_code:
            postcode, created = _upsert_postcode(street, link, postcode_code)
            _increment_stat(
                run, "postcodes_created" if created else "postcodes_updated"
            )
        return

    raise ValueError(f"unsupported_sync_level:{level}")


def sync_run_to_dict(run: TanzaniaAddressSyncRun) -> dict[str, object]:
    progress = _sync_progress_fields(run)
    return {
        "id": str(run.id),
        "mode": run.mode,
        "status": run.status,
        "source_root": run.source_root,
        "pages_processed": run.pages_processed,
        "request_budget": run.request_budget,
        "throttle_seconds": run.throttle_seconds,
        **progress,
        "stats": dict(run.stats or {}),
        "country_code": "TZ",
        "last_error": run.last_error or None,
        "triggered_by": run.triggered_by or None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "next_not_before_at": (
            run.next_not_before_at.isoformat() if run.next_not_before_at else None
        ),
    }


def process_tanzania_address_sync_run(
    run: TanzaniaAddressSyncRun,
    *,
    fetcher: Callable[[str], str] = fetch_html,
) -> dict[str, object]:
    ensure_sync_seed_queue(run)
    if not run.started_at:
        run.started_at = timezone.now()
    now = timezone.now()
    if run.next_not_before_at and now < run.next_not_before_at:
        run.status = TanzaniaAddressSyncRun.Status.PAUSED
        run.save(
            update_fields=[
                "checkpoint",
                "stats",
                "started_at",
                "status",
                "next_not_before_at",
                "updated_at",
            ]
        )
        return sync_run_to_dict(run)

    run.status = TanzaniaAddressSyncRun.Status.RUNNING
    run.last_error = ""
    run.save(
        update_fields=[
            "checkpoint",
            "stats",
            "started_at",
            "status",
            "last_error",
            "updated_at",
        ]
    )

    remaining_budget = max(1, run.request_budget)
    try:
        while remaining_budget > 0:
            queue = _queue_items(run)
            if not queue:
                run.status = TanzaniaAddressSyncRun.Status.COMPLETED
                run.completed_at = timezone.now()
                run.next_not_before_at = run.completed_at
                run.save(
                    update_fields=[
                        "checkpoint",
                        "stats",
                        "status",
                        "completed_at",
                        "next_not_before_at",
                        "updated_at",
                    ]
                )
                return sync_run_to_dict(run)

            item = queue.pop(0)
            _replace_queue(run, queue)
            try:
                html = fetcher(item["url"])
            except AddressSyncFetchError as exc:
                _increment_stat(run, "failure_count")
                run.status = TanzaniaAddressSyncRun.Status.PAUSED
                run.last_error = str(exc)
                run.next_not_before_at = timezone.now() + timedelta(
                    seconds=max(run.throttle_seconds, 5)
                )
                run.save(
                    update_fields=[
                        "checkpoint",
                        "stats",
                        "status",
                        "last_error",
                        "next_not_before_at",
                        "updated_at",
                    ]
                )
                return sync_run_to_dict(run)

            with transaction.atomic():
                _process_item(run, item, html)
                run.pages_processed += 1
                run.next_not_before_at = timezone.now() + timedelta(
                    seconds=run.throttle_seconds
                )
                run.save(
                    update_fields=[
                        "checkpoint",
                        "stats",
                        "pages_processed",
                        "next_not_before_at",
                        "updated_at",
                    ]
                )
            remaining_budget -= 1
    except Exception as exc:
        _increment_stat(run, "failure_count")
        run.status = TanzaniaAddressSyncRun.Status.FAILED
        run.last_error = str(exc)
        run.save(update_fields=["stats", "status", "last_error", "updated_at"])
        raise

    run.status = TanzaniaAddressSyncRun.Status.PAUSED
    run.save(update_fields=["status", "updated_at"])
    return sync_run_to_dict(run)


@dataclass
class MetadataValidationResult:
    valid: bool
    errors: list[dict[str, str]]
    normalized_data: dict[str, object]


@dataclass
class WorkflowTemplateValidationResult:
    valid: bool
    errors: list[dict[str, str]]
    compiled_definition: dict[str, object]


@dataclass
class OperationVersionValidationResult:
    valid: bool
    errors: list[dict[str, str]]


@dataclass
class FormPackageValidationResult:
    valid: bool
    errors: list[dict[str, str]]
    compiled_projection: dict[str, object]


@dataclass(frozen=True)
class ReferenceOperationProvisionError(Exception):
    code: str
    details: list[dict[str, str]] | None = None


@dataclass(frozen=True)
class SampleAccessionReferenceBundle:
    form_package: FormPackage
    form_package_version: FormPackageVersion
    workflow_template: WorkflowTemplate
    workflow_version: WorkflowTemplateVersion
    operation_definition: OperationDefinition
    operation_version: OperationVersion
    created: bool


@dataclass(frozen=True)
class SampleAccessionAdapterResult:
    operation_run: OperationRun
    qc_result: QCResult | None
    biospecimen: Biospecimen | None = None
    event: ReceivingEvent | None = None
    manifest_item: AccessioningManifestItem | None = None
    discrepancy: ReceivingDiscrepancy | None = None


@dataclass
class OperationTaskTransitionResult:
    task_run: TaskRun
    operation_run: OperationRun
    created_tasks: list[TaskRun]
    submission: SubmissionRecord | None = None
    approval: ApprovalRecord | None = None


def _condition_matches(
    condition: dict[str, object], payload: dict[str, object]
) -> bool:
    if not condition:
        return True
    field_key = str(condition.get("field") or "").strip()
    operator = str(condition.get("operator") or "equals").strip()
    if not field_key:
        return True
    lhs = payload.get(field_key)
    rhs = condition.get("value")
    if operator == "equals":
        return lhs == rhs
    if operator == "not_equals":
        return lhs != rhs
    if operator == "in":
        return lhs in (rhs or [])
    if operator == "not_in":
        return lhs not in (rhs or [])
    if operator == "truthy":
        return bool(lhs)
    if operator == "falsy":
        return not bool(lhs)
    if operator in {"gt", "gte", "lt", "lte"}:
        try:
            left_number = Decimal(str(lhs))
            right_number = Decimal(str(rhs))
        except (InvalidOperation, TypeError, ValueError):
            return False
        if operator == "gt":
            return left_number > right_number
        if operator == "gte":
            return left_number >= right_number
        if operator == "lt":
            return left_number < right_number
        return left_number <= right_number
    return False


def _stable_oid(prefix: str, key: str) -> str:
    normalized = slugify(key).replace("-", "_").upper()
    if not normalized:
        normalized = uuid.uuid4().hex[:12].upper()
    return f"{prefix}.{normalized}"


def _sample_accession_reference_sop_version_label(version_number: int) -> str:
    return f"sample-accession-reference-sop-v{version_number}"


def _sample_accession_reference_runtime_defaults() -> dict[str, object]:
    return {
        "reference_operation": SAMPLE_ACCESSION_REFERENCE_OPERATION_CODE,
        "source_modes": list(SAMPLE_ACCESSION_REFERENCE_SOURCE_MODES),
        "task_keys": dict(SAMPLE_ACCESSION_REFERENCE_TASK_KEYS),
        "transitional_adapters": list(SAMPLE_ACCESSION_REFERENCE_TRANSITIONAL_ADAPTERS),
        "sop_context_required": True,
    }


def _sample_accession_reference_bundle_errors(
    *,
    form_package_version: FormPackageVersion,
    workflow_version: WorkflowTemplateVersion,
    operation_version: OperationVersion,
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []

    compiler_context = dict(form_package_version.compiler_context or {})
    if form_package_version.package.code != SAMPLE_ACCESSION_REFERENCE_PACKAGE_CODE:
        errors.append(
            {
                "field": "form_package.code",
                "code": "reference_package_code_mismatch",
            }
        )
    if (
        compiler_context.get("reference_operation")
        != SAMPLE_ACCESSION_REFERENCE_OPERATION_CODE
    ):
        errors.append(
            {
                "field": "form_package_version.compiler_context.reference_operation",
                "code": "reference_operation_mismatch",
            }
        )
    if compiler_context.get("bundle_kind") != "reference_operation":
        errors.append(
            {
                "field": "form_package_version.compiler_context.bundle_kind",
                "code": "bundle_kind_mismatch",
            }
        )
    if compiler_context.get("source_kind") != "canonical_reference_bundle":
        errors.append(
            {
                "field": "form_package_version.compiler_context.source_kind",
                "code": "source_kind_mismatch",
            }
        )

    compiled_projection = (
        form_package_version.compiled_projection.projection
        if hasattr(form_package_version, "compiled_projection")
        else {}
    )
    section_keys = [
        str(item.get("section_key") or "")
        for item in compiled_projection.get("sections") or []
    ]
    if section_keys != SAMPLE_ACCESSION_REFERENCE_SECTION_KEYS:
        errors.append(
            {
                "field": "form_package_version.compiled_projection.sections",
                "code": "reference_sections_mismatch",
            }
        )

    if workflow_version.template.code != SAMPLE_ACCESSION_REFERENCE_OPERATION_CODE:
        errors.append(
            {
                "field": "workflow_template.code",
                "code": "reference_workflow_code_mismatch",
            }
        )
    compiled_definition = dict(workflow_version.compiled_definition or {})
    node_map = {
        str(node.get("node_key") or ""): node
        for node in compiled_definition.get("nodes") or []
    }
    qc_node = node_map.get("qc_decision")
    if not qc_node:
        errors.append(
            {
                "field": "workflow_version.compiled_definition.nodes",
                "code": "reference_qc_node_missing",
            }
        )
    else:
        if not bool((qc_node.get("approval") or {}).get("required")):
            errors.append(
                {
                    "field": "workflow_version.compiled_definition.nodes.qc_decision.approval",
                    "code": "reference_qc_approval_required",
                }
            )
        bindings = qc_node.get("bindings") or []
        item_keys = []
        if bindings:
            item_keys = list(bindings[0].get("item_keys") or [])
        if item_keys != SAMPLE_ACCESSION_REFERENCE_QC_BINDING_ITEM_KEYS:
            errors.append(
                {
                    "field": "workflow_version.compiled_definition.nodes.qc_decision.bindings",
                    "code": "reference_qc_binding_mismatch",
                }
            )
    intake_node = node_map.get("intake_capture")
    if not intake_node:
        errors.append(
            {
                "field": "workflow_version.compiled_definition.nodes",
                "code": "reference_intake_node_missing",
            }
        )
    else:
        intake_config = dict(intake_node.get("config") or {})
        if intake_config.get("source_modes") != SAMPLE_ACCESSION_REFERENCE_SOURCE_MODES:
            errors.append(
                {
                    "field": "workflow_version.compiled_definition.nodes.intake_capture.config.source_modes",
                    "code": "reference_source_modes_mismatch",
                }
            )
        if intake_config.get("adapter_surface") != reverse("lims_receiving_page"):
            errors.append(
                {
                    "field": "workflow_version.compiled_definition.nodes.intake_capture.config.adapter_surface",
                    "code": "reference_adapter_surface_mismatch",
                }
            )

    expected_runtime_defaults = _sample_accession_reference_runtime_defaults()
    if operation_version.definition.code != SAMPLE_ACCESSION_REFERENCE_OPERATION_CODE:
        errors.append(
            {
                "field": "operation_definition.code",
                "code": "reference_operation_code_mismatch",
            }
        )
    if operation_version.workflow_version_id != workflow_version.id:
        errors.append(
            {
                "field": "operation_version.workflow_version",
                "code": "reference_operation_workflow_mismatch",
            }
        )
    if dict(operation_version.runtime_defaults or {}) != expected_runtime_defaults:
        errors.append(
            {
                "field": "operation_version.runtime_defaults",
                "code": "reference_runtime_defaults_mismatch",
            }
        )
    expected_sop_label = _sample_accession_reference_sop_version_label(
        operation_version.version_number
    )
    if operation_version.sop_version_label != expected_sop_label:
        errors.append(
            {
                "field": "operation_version.sop_version_label",
                "code": "reference_sop_version_label_mismatch",
            }
        )

    return errors


def _assert_sample_accession_reference_bundle_invariants(
    bundle: SampleAccessionReferenceBundle,
) -> None:
    errors = _sample_accession_reference_bundle_errors(
        form_package_version=bundle.form_package_version,
        workflow_version=bundle.workflow_version,
        operation_version=bundle.operation_version,
    )
    if errors:
        raise ReferenceOperationProvisionError(
            "sample_accession_reference_bundle_invariants_failed",
            errors,
        )


def bootstrap_form_package_version_from_schema_version(
    *,
    schema_version: MetadataSchemaVersion,
    target_version: FormPackageVersion,
) -> None:
    section_map: dict[str, FormPackageSection] = {}
    choice_list_map: dict[str, FormPackageChoiceList] = {}
    fields = (
        schema_version.fields.select_related("vocabulary")
        .prefetch_related("vocabulary__items")
        .order_by("position", "field_key")
    )
    for index, field in enumerate(fields, start=1):
        ui_step = str((field.config or {}).get("ui_step") or "main").strip() or "main"
        section_key = slugify(ui_step) or f"section-{index}"
        if section_key not in section_map:
            section_map[section_key] = FormPackageSection.objects.create(
                version=target_version,
                section_key=section_key,
                oid=_stable_oid("SEC", section_key),
                title=ui_step.replace("-", " ").replace("_", " ").title(),
                description=f"Bootstrapped from metadata schema step '{ui_step}'.",
                position=len(section_map) + 1,
                config={"source_ui_step": ui_step},
            )
        choice_list = None
        if field.vocabulary_id:
            choice_list_key = (
                slugify(field.vocabulary.code or field.field_key) or f"choices-{index}"
            )
            choice_list = choice_list_map.get(choice_list_key)
            if choice_list is None:
                choice_list = FormPackageChoiceList.objects.create(
                    version=target_version,
                    vocabulary=field.vocabulary,
                    list_key=choice_list_key,
                    oid=_stable_oid("CL", choice_list_key),
                    title=field.vocabulary.name,
                    description=field.vocabulary.description,
                    position=len(choice_list_map) + 1,
                )
                choice_list_map[choice_list_key] = choice_list
                for choice_index, vocabulary_item in enumerate(
                    field.vocabulary.items.filter(is_active=True).order_by(
                        "sort_order", "label"
                    ),
                    start=1,
                ):
                    FormPackageChoice.objects.create(
                        choice_list=choice_list,
                        value=vocabulary_item.value,
                        label=vocabulary_item.label,
                        sort_order=choice_index,
                        is_active=vocabulary_item.is_active,
                    )
        FormPackageItem.objects.create(
            version=target_version,
            section=section_map[section_key],
            choice_list=choice_list,
            item_key=field.field_key,
            oid=_stable_oid("ITEM", field.field_key),
            question_text=field.name,
            prompt_text=field.description,
            field_type=field.field_type,
            help_text=field.help_text,
            placeholder=field.placeholder,
            default_value=field.default_value,
            position=field.position or index,
            required=field.required,
            validation_rules=dict(field.validation_rules or {}),
            config=dict(field.config or {}),
            source_field_key=field.field_key,
        )


def clone_form_package_version(
    *,
    source_version: FormPackageVersion,
    target_version: FormPackageVersion,
) -> None:
    section_map: dict[str, FormPackageSection] = {}
    choice_list_map: dict[str, FormPackageChoiceList] = {}
    item_group_map: dict[str, FormPackageItemGroup] = {}
    for section in source_version.sections.all().order_by("position", "section_key"):
        cloned_section = FormPackageSection.objects.create(
            version=target_version,
            section_key=section.section_key,
            oid=section.oid,
            title=section.title,
            description=section.description,
            position=section.position,
            config=dict(section.config or {}),
        )
        section_map[str(section.id)] = cloned_section
    for choice_list in (
        source_version.choice_lists.prefetch_related("choices")
        .all()
        .order_by("position", "list_key")
    ):
        cloned_choice_list = FormPackageChoiceList.objects.create(
            version=target_version,
            vocabulary=choice_list.vocabulary,
            list_key=choice_list.list_key,
            oid=choice_list.oid,
            title=choice_list.title,
            description=choice_list.description,
            position=choice_list.position,
        )
        choice_list_map[str(choice_list.id)] = cloned_choice_list
        for choice in choice_list.choices.all():
            FormPackageChoice.objects.create(
                choice_list=cloned_choice_list,
                value=choice.value,
                label=choice.label,
                sort_order=choice.sort_order,
                is_active=choice.is_active,
            )
    for group in (
        source_version.item_groups.select_related("section")
        .all()
        .order_by("position", "group_key")
    ):
        cloned_group = FormPackageItemGroup.objects.create(
            version=target_version,
            section=section_map[str(group.section_id)],
            group_key=group.group_key,
            oid=group.oid,
            title=group.title,
            description=group.description,
            position=group.position,
            repeats=group.repeats,
            config=dict(group.config or {}),
        )
        item_group_map[str(group.id)] = cloned_group
    for item in (
        source_version.items.select_related("section", "item_group", "choice_list")
        .all()
        .order_by("section__position", "position", "item_key")
    ):
        FormPackageItem.objects.create(
            version=target_version,
            section=section_map[str(item.section_id)],
            item_group=(
                item_group_map.get(str(item.item_group_id))
                if item.item_group_id
                else None
            ),
            choice_list=(
                choice_list_map.get(str(item.choice_list_id))
                if item.choice_list_id
                else None
            ),
            item_key=item.item_key,
            oid=item.oid,
            question_text=item.question_text,
            prompt_text=item.prompt_text,
            field_type=item.field_type,
            help_text=item.help_text,
            placeholder=item.placeholder,
            default_value=item.default_value,
            position=item.position,
            required=item.required,
            validation_rules=dict(item.validation_rules or {}),
            config=dict(item.config or {}),
            source_field_key=item.source_field_key,
        )
    for artifact in source_version.source_artifacts.all().order_by(
        "created_at", "filename"
    ):
        FormPackageSourceArtifact.objects.create(
            version=target_version,
            role=artifact.role,
            artifact_type=artifact.artifact_type,
            filename=artifact.filename,
            content_type=artifact.content_type,
            checksum=artifact.checksum,
            storage_key=artifact.storage_key,
            artifact_metadata=dict(artifact.artifact_metadata or {}),
        )


def validate_form_package_version(
    version: FormPackageVersion,
) -> FormPackageValidationResult:
    sections = list(version.sections.all().order_by("position", "section_key"))
    choice_lists = list(
        version.choice_lists.prefetch_related("choices")
        .all()
        .order_by("position", "list_key")
    )
    item_groups = list(
        version.item_groups.select_related("section")
        .all()
        .order_by("position", "group_key")
    )
    items = list(
        version.items.select_related("section", "item_group", "choice_list")
        .all()
        .order_by("section__position", "position", "item_key")
    )
    errors: list[dict[str, str]] = []

    if not sections:
        errors.append({"field": "sections", "code": "version_requires_sections"})
    if not items:
        errors.append({"field": "items", "code": "version_requires_items"})

    seen_oids: dict[str, str] = {}
    for prefix, collection in (
        ("section", sections),
        ("choice_list", choice_lists),
        ("item_group", item_groups),
        ("item", items),
    ):
        for item in collection:
            key = getattr(
                item,
                "section_key",
                getattr(
                    item,
                    "list_key",
                    getattr(item, "group_key", getattr(item, "item_key", "unknown")),
                ),
            )
            if item.oid in seen_oids:
                errors.append(
                    {
                        "field": f"{prefix}s.{key}",
                        "code": "duplicate_oid",
                        "detail": item.oid,
                    }
                )
            else:
                seen_oids[item.oid] = prefix

    choice_types = {
        MetadataFieldDefinition.FieldType.CHOICE,
        MetadataFieldDefinition.FieldType.MULTI_CHOICE,
    }
    for item in items:
        if item.field_type in choice_types and not item.choice_list_id:
            errors.append(
                {"field": f"items.{item.item_key}", "code": "choice_list_required"}
            )
        if item.field_type not in choice_types and item.choice_list_id:
            errors.append(
                {"field": f"items.{item.item_key}", "code": "choice_list_not_allowed"}
            )
        if item.item_group_id and item.item_group.section_id != item.section_id:
            errors.append(
                {
                    "field": f"items.{item.item_key}",
                    "code": "item_group_section_mismatch",
                }
            )

    choice_projection = {
        str(choice_list.id): {
            "id": str(choice_list.id),
            "list_key": choice_list.list_key,
            "oid": choice_list.oid,
            "title": choice_list.title,
            "description": choice_list.description,
            "vocabulary_id": (
                str(choice_list.vocabulary_id) if choice_list.vocabulary_id else None
            ),
            "choices": [
                {
                    "id": str(choice.id),
                    "value": choice.value,
                    "label": choice.label,
                    "sort_order": choice.sort_order,
                    "is_active": choice.is_active,
                }
                for choice in choice_list.choices.all().order_by("sort_order", "label")
            ],
        }
        for choice_list in choice_lists
    }
    groups_by_section: dict[str, list[dict[str, object]]] = {
        str(section.id): [] for section in sections
    }
    group_items: dict[str, list[dict[str, object]]] = {
        str(group.id): [] for group in item_groups
    }
    section_items: dict[str, list[dict[str, object]]] = {
        str(section.id): [] for section in sections
    }

    for item in items:
        item_dict = {
            "id": str(item.id),
            "item_key": item.item_key,
            "oid": item.oid,
            "question_text": item.question_text,
            "prompt_text": item.prompt_text,
            "field_type": item.field_type,
            "required": item.required,
            "position": item.position,
            "help_text": item.help_text,
            "placeholder": item.placeholder,
            "default_value": item.default_value,
            "validation_rules": dict(item.validation_rules or {}),
            "config": dict(item.config or {}),
            "source_field_key": item.source_field_key or None,
            "choice_list_id": str(item.choice_list_id) if item.choice_list_id else None,
        }
        if item.item_group_id:
            group_items[str(item.item_group_id)].append(item_dict)
        else:
            section_items[str(item.section_id)].append(item_dict)

    for group in item_groups:
        groups_by_section[str(group.section_id)].append(
            {
                "id": str(group.id),
                "group_key": group.group_key,
                "oid": group.oid,
                "title": group.title,
                "description": group.description,
                "position": group.position,
                "repeats": group.repeats,
                "config": dict(group.config or {}),
                "items": group_items[str(group.id)],
            }
        )

    compiled_projection = {
        "package_id": str(version.package_id),
        "package_code": version.package.code,
        "package_name": version.package.name,
        "version_id": str(version.id),
        "version_number": version.version_number,
        "source_schema_version_id": (
            str(version.source_schema_version_id)
            if version.source_schema_version_id
            else None
        ),
        "sections": [
            {
                "id": str(section.id),
                "section_key": section.section_key,
                "oid": section.oid,
                "title": section.title,
                "description": section.description,
                "position": section.position,
                "config": dict(section.config or {}),
                "items": section_items[str(section.id)],
                "item_groups": groups_by_section[str(section.id)],
            }
            for section in sections
        ],
        "choice_lists": list(choice_projection.values()),
        "compiler_context": dict(version.compiler_context or {}),
    }
    return FormPackageValidationResult(
        valid=not errors, errors=errors, compiled_projection=compiled_projection
    )


def replace_form_package_diagnostics(
    *,
    version: FormPackageVersion,
    errors: list[dict[str, str]],
) -> None:
    version.compiler_diagnostics.all().delete()
    if errors:
        for error in errors:
            FormPackageCompilerDiagnostic.objects.create(
                version=version,
                severity=FormPackageCompilerDiagnostic.Severity.ERROR,
                stage=FormPackageCompilerDiagnostic.Stage.VALIDATE,
                code=str(error.get("code") or "validation_error"),
                pointer=str(error.get("field") or ""),
                message=str(
                    error.get("detail") or error.get("code") or "Validation error"
                ),
                details=dict(error),
            )
        return
    FormPackageCompilerDiagnostic.objects.create(
        version=version,
        severity=FormPackageCompilerDiagnostic.Severity.INFO,
        stage=FormPackageCompilerDiagnostic.Stage.COMPILE,
        code="compiled_projection_ready",
        pointer="compiled_projection",
        message="Compiled projection generated successfully.",
        details={},
    )


def publish_form_package_version(
    version: FormPackageVersion,
) -> FormPackageValidationResult:
    result = validate_form_package_version(version)
    with transaction.atomic():
        replace_form_package_diagnostics(version=version, errors=result.errors)
        if result.valid:
            FormPackageVersion.objects.filter(
                package_id=version.package_id,
                status=FormPackageVersion.Status.PUBLISHED,
            ).exclude(id=version.id).update(status=FormPackageVersion.Status.DEPRECATED)
            version.status = FormPackageVersion.Status.PUBLISHED
            version.save(update_fields=["status", "updated_at"])
            FormPackageProjection.objects.update_or_create(
                version=version,
                defaults={"projection": result.compiled_projection},
            )
    return result


def _publish_workflow_template_version(
    version: WorkflowTemplateVersion,
) -> WorkflowTemplateValidationResult:
    result = validate_workflow_template_version(version)
    if not result.valid:
        raise ReferenceOperationProvisionError(
            "workflow_validation_failed", result.errors
        )
    WorkflowTemplateVersion.objects.filter(
        template_id=version.template_id,
        status=WorkflowTemplateVersion.Status.PUBLISHED,
    ).exclude(id=version.id).update(status=WorkflowTemplateVersion.Status.DEPRECATED)
    version.status = WorkflowTemplateVersion.Status.PUBLISHED
    version.compiled_definition = result.compiled_definition
    version.save(update_fields=["status", "compiled_definition", "updated_at"])
    return result


def _publish_operation_version(
    version: OperationVersion,
) -> OperationVersionValidationResult:
    result = validate_operation_version(version)
    if not result.valid:
        raise ReferenceOperationProvisionError(
            "operation_validation_failed", result.errors
        )
    OperationVersion.objects.filter(
        definition_id=version.definition_id,
        status=OperationVersion.Status.PUBLISHED,
    ).exclude(id=version.id).update(status=OperationVersion.Status.DEPRECATED)
    version.status = OperationVersion.Status.PUBLISHED
    version.save(update_fields=["status", "updated_at"])
    return result


def _create_sample_accession_form_package_version(
    *, package: FormPackage
) -> FormPackageVersion:
    version = FormPackageVersion.objects.create(
        package=package,
        version_number=(
            package.versions.order_by("-version_number")
            .values_list("version_number", flat=True)
            .first()
            or 0
        )
        + 1,
        change_summary="Canonical sample accession reference package.",
        compiler_context={
            "reference_operation": SAMPLE_ACCESSION_REFERENCE_OPERATION_CODE,
            "bundle_kind": "reference_operation",
            "source_kind": "canonical_reference_bundle",
        },
    )
    intake_section = FormPackageSection.objects.create(
        version=version,
        section_key="intake",
        oid=_stable_oid("SEC", "sample-accession-intake"),
        title="Intake",
        description="Primary intake metadata captured when a sample first arrives.",
        position=1,
        config={"ui_step": "intake"},
    )
    qc_section = FormPackageSection.objects.create(
        version=version,
        section_key="qc",
        oid=_stable_oid("SEC", "sample-accession-qc"),
        title="QC decision",
        description="Quality-control disposition captured before storage or rejection.",
        position=2,
        config={"ui_step": "qc"},
    )
    storage_section = FormPackageSection.objects.create(
        version=version,
        section_key="storage",
        oid=_stable_oid("SEC", "sample-accession-storage"),
        title="Storage",
        description="Initial storage placement captured after acceptance.",
        position=3,
        config={"ui_step": "storage"},
    )
    rejection_section = FormPackageSection.objects.create(
        version=version,
        section_key="rejection",
        oid=_stable_oid("SEC", "sample-accession-rejection"),
        title="Rejection",
        description="Explicit rejection reason and discrepancy coding for refused samples.",
        position=4,
        config={"ui_step": "rejection"},
    )
    qc_choice_list = FormPackageChoiceList.objects.create(
        version=version,
        list_key="qc-decision",
        oid=_stable_oid("CL", "sample-accession-qc-decision"),
        title="QC decision",
        description="Canonical accession QC disposition.",
        position=1,
    )
    FormPackageChoice.objects.bulk_create(
        [
            FormPackageChoice(
                choice_list=qc_choice_list, value="accept", label="Accept", sort_order=1
            ),
            FormPackageChoice(
                choice_list=qc_choice_list, value="reject", label="Reject", sort_order=2
            ),
        ]
    )
    FormPackageItem.objects.bulk_create(
        [
            FormPackageItem(
                version=version,
                section=intake_section,
                item_key="subject_identifier",
                oid=_stable_oid("ITEM", "sample-accession-subject-identifier"),
                question_text="Subject identifier",
                field_type=MetadataFieldDefinition.FieldType.TEXT,
                position=1,
                required=True,
                config={"semantic_key": "subject_identifier"},
            ),
            FormPackageItem(
                version=version,
                section=intake_section,
                item_key="external_identifier",
                oid=_stable_oid("ITEM", "sample-accession-external-identifier"),
                question_text="External identifier",
                field_type=MetadataFieldDefinition.FieldType.TEXT,
                position=2,
                required=False,
                config={"semantic_key": "external_identifier"},
            ),
            FormPackageItem(
                version=version,
                section=intake_section,
                item_key="sample_identifier",
                oid=_stable_oid("ITEM", "sample-accession-sample-identifier"),
                question_text="Sample identifier",
                field_type=MetadataFieldDefinition.FieldType.TEXT,
                position=3,
                required=False,
            ),
            FormPackageItem(
                version=version,
                section=intake_section,
                item_key="barcode",
                oid=_stable_oid("ITEM", "sample-accession-barcode"),
                question_text="Barcode",
                field_type=MetadataFieldDefinition.FieldType.TEXT,
                position=4,
                required=False,
            ),
            FormPackageItem(
                version=version,
                section=intake_section,
                item_key="received_at",
                oid=_stable_oid("ITEM", "sample-accession-received-at"),
                question_text="Received at",
                field_type=MetadataFieldDefinition.FieldType.DATE,
                position=5,
                required=True,
            ),
            FormPackageItem(
                version=version,
                section=intake_section,
                item_key="quantity",
                oid=_stable_oid("ITEM", "sample-accession-quantity"),
                question_text="Quantity",
                field_type=MetadataFieldDefinition.FieldType.DECIMAL,
                position=6,
                required=False,
            ),
            FormPackageItem(
                version=version,
                section=intake_section,
                item_key="quantity_unit",
                oid=_stable_oid("ITEM", "sample-accession-quantity-unit"),
                question_text="Quantity unit",
                field_type=MetadataFieldDefinition.FieldType.TEXT,
                position=7,
                required=False,
                default_value="mL",
            ),
            FormPackageItem(
                version=version,
                section=intake_section,
                item_key="source_reference",
                oid=_stable_oid("ITEM", "sample-accession-source-reference"),
                question_text="Source reference",
                field_type=MetadataFieldDefinition.FieldType.TEXT,
                position=8,
                required=False,
            ),
            FormPackageItem(
                version=version,
                section=intake_section,
                item_key="brought_by",
                oid=_stable_oid("ITEM", "sample-accession-brought-by"),
                question_text="Brought by",
                field_type=MetadataFieldDefinition.FieldType.TEXT,
                position=9,
                required=False,
            ),
            FormPackageItem(
                version=version,
                section=qc_section,
                choice_list=qc_choice_list,
                item_key="qc_decision",
                oid=_stable_oid("ITEM", "sample-accession-qc-decision"),
                question_text="QC decision",
                field_type=MetadataFieldDefinition.FieldType.CHOICE,
                position=1,
                required=True,
                config={"semantic_key": "qc_decision"},
            ),
            FormPackageItem(
                version=version,
                section=qc_section,
                item_key="qc_notes",
                oid=_stable_oid("ITEM", "sample-accession-qc-notes"),
                question_text="QC notes",
                field_type=MetadataFieldDefinition.FieldType.LONG_TEXT,
                position=2,
                required=False,
            ),
            FormPackageItem(
                version=version,
                section=storage_section,
                item_key="storage_reference",
                oid=_stable_oid("ITEM", "sample-accession-storage-reference"),
                question_text="Storage reference",
                field_type=MetadataFieldDefinition.FieldType.TEXT,
                position=1,
                required=True,
                config={"semantic_key": "storage_reference"},
            ),
            FormPackageItem(
                version=version,
                section=storage_section,
                item_key="storage_notes",
                oid=_stable_oid("ITEM", "sample-accession-storage-notes"),
                question_text="Storage notes",
                field_type=MetadataFieldDefinition.FieldType.LONG_TEXT,
                position=2,
                required=False,
            ),
            FormPackageItem(
                version=version,
                section=rejection_section,
                item_key="rejection_code",
                oid=_stable_oid("ITEM", "sample-accession-rejection-code"),
                question_text="Rejection code",
                field_type=MetadataFieldDefinition.FieldType.TEXT,
                position=1,
                required=False,
            ),
            FormPackageItem(
                version=version,
                section=rejection_section,
                item_key="reason",
                oid=_stable_oid("ITEM", "sample-accession-reason"),
                question_text="Rejection reason",
                field_type=MetadataFieldDefinition.FieldType.LONG_TEXT,
                position=2,
                required=False,
                config={"semantic_key": "rejection_reason"},
            ),
        ]
    )
    FormPackageSourceArtifact.objects.create(
        version=version,
        role=FormPackageSourceArtifact.Role.SOURCE,
        artifact_type=FormPackageSourceArtifact.ArtifactType.JSON,
        filename="sample-accession.reference.bundle.json",
        content_type="application/json",
        artifact_metadata={
            "reference_operation": SAMPLE_ACCESSION_REFERENCE_OPERATION_CODE,
            "source_kind": "canonical_reference_bundle",
        },
    )
    result = publish_form_package_version(version)
    if not result.valid:
        raise ReferenceOperationProvisionError(
            "form_package_validation_failed", result.errors
        )
    version.refresh_from_db()
    return version


def _create_sample_accession_workflow_version(
    *,
    template: WorkflowTemplate,
    form_package_version: FormPackageVersion,
) -> WorkflowTemplateVersion:
    version = WorkflowTemplateVersion.objects.create(
        template=template,
        version_number=(
            template.versions.order_by("-version_number")
            .values_list("version_number", flat=True)
            .first()
            or 0
        )
        + 1,
        change_summary="Canonical sample accession reference workflow.",
    )
    start_node = WorkflowNodeTemplate.objects.create(
        workflow_version=version,
        node_key="start",
        node_type=WorkflowNodeTemplate.NodeType.START,
        title="Start",
        position=1,
    )
    intake_node = WorkflowNodeTemplate.objects.create(
        workflow_version=version,
        node_key="intake_capture",
        node_type=WorkflowNodeTemplate.NodeType.VIEW,
        title="Intake capture",
        summary="Capture initial accession metadata for the inbound sample.",
        position=2,
        assignment_role="lims.operator",
        permission_key="lims.workflow_task.execute",
        config={
            "source_modes": list(SAMPLE_ACCESSION_REFERENCE_SOURCE_MODES),
            "adapter_surface": reverse("lims_receiving_page"),
        },
    )
    qc_node = WorkflowNodeTemplate.objects.create(
        workflow_version=version,
        node_key="qc_decision",
        node_type=WorkflowNodeTemplate.NodeType.IF,
        title="QC decision",
        summary="Record the first QC disposition and require QA confirmation.",
        position=3,
        assignment_role="lims.operator",
        permission_key="lims.workflow_task.execute",
        requires_approval=True,
        approval_role="lims.qa",
    )
    storage_node = WorkflowNodeTemplate.objects.create(
        workflow_version=version,
        node_key="storage_logging",
        node_type=WorkflowNodeTemplate.NodeType.VIEW,
        title="Storage logging",
        summary="Capture the first accepted storage placement.",
        position=4,
        assignment_role="lims.operator",
        permission_key="lims.workflow_task.execute",
    )
    accepted_end = WorkflowNodeTemplate.objects.create(
        workflow_version=version,
        node_key="accepted_end",
        node_type=WorkflowNodeTemplate.NodeType.END,
        title="Accepted",
        position=5,
    )
    rejected_end = WorkflowNodeTemplate.objects.create(
        workflow_version=version,
        node_key="rejected_end",
        node_type=WorkflowNodeTemplate.NodeType.END,
        title="Rejected",
        position=6,
    )
    WorkflowStepBinding.objects.bulk_create(
        [
            WorkflowStepBinding(
                node=intake_node,
                form_package_version=form_package_version,
                binding_type=WorkflowStepBinding.BindingType.SECTION_SET,
                section_keys=["intake"],
            ),
            WorkflowStepBinding(
                node=qc_node,
                form_package_version=form_package_version,
                binding_type=WorkflowStepBinding.BindingType.ITEM_SET,
                item_keys=list(SAMPLE_ACCESSION_REFERENCE_QC_BINDING_ITEM_KEYS),
            ),
            WorkflowStepBinding(
                node=storage_node,
                form_package_version=form_package_version,
                binding_type=WorkflowStepBinding.BindingType.SECTION_SET,
                section_keys=["storage"],
            ),
        ]
    )
    WorkflowEdgeTemplate.objects.bulk_create(
        [
            WorkflowEdgeTemplate(
                workflow_version=version,
                source_node=start_node,
                target_node=intake_node,
                priority=1,
            ),
            WorkflowEdgeTemplate(
                workflow_version=version,
                source_node=intake_node,
                target_node=qc_node,
                priority=1,
            ),
            WorkflowEdgeTemplate(
                workflow_version=version,
                source_node=qc_node,
                target_node=storage_node,
                priority=1,
                condition={
                    "item_key": "qc_decision",
                    "operator": "equals",
                    "value": "accept",
                },
            ),
            WorkflowEdgeTemplate(
                workflow_version=version,
                source_node=qc_node,
                target_node=rejected_end,
                priority=2,
                condition={
                    "item_key": "qc_decision",
                    "operator": "equals",
                    "value": "reject",
                },
            ),
            WorkflowEdgeTemplate(
                workflow_version=version,
                source_node=storage_node,
                target_node=accepted_end,
                priority=1,
            ),
        ]
    )
    _publish_workflow_template_version(version)
    version.refresh_from_db()
    return version


def _create_sample_accession_operation_version(
    *,
    definition: OperationDefinition,
    workflow_version: WorkflowTemplateVersion,
) -> OperationVersion:
    version = OperationVersion.objects.create(
        definition=definition,
        workflow_version=workflow_version,
        version_number=(
            definition.versions.order_by("-version_number")
            .values_list("version_number", flat=True)
            .first()
            or 0
        )
        + 1,
        change_summary="Canonical sample accession reference operation.",
        sop_version_label=_sample_accession_reference_sop_version_label(
            (
                definition.versions.order_by("-version_number")
                .values_list("version_number", flat=True)
                .first()
                or 0
            )
            + 1
        ),
        runtime_defaults=_sample_accession_reference_runtime_defaults(),
    )
    _publish_operation_version(version)
    version.refresh_from_db()
    return version


@transaction.atomic
def provision_sample_accession_reference_bundle() -> SampleAccessionReferenceBundle:
    created = False
    form_package, package_created = FormPackage.objects.get_or_create(
        code=SAMPLE_ACCESSION_REFERENCE_PACKAGE_CODE,
        defaults={
            "name": "Sample accession package",
            "description": "Compiler-owned canonical form package for the sample accession reference operation.",
            "purpose": "Reference sample accession capture contract",
            "module_scope": FormPackage.ModuleScope.LIMS,
            "is_active": True,
        },
    )
    created = created or package_created
    form_package_version = (
        form_package.versions.filter(status=FormPackageVersion.Status.PUBLISHED)
        .order_by("-version_number")
        .first()
    )
    if form_package_version is None:
        form_package_version = _create_sample_accession_form_package_version(
            package=form_package
        )
        created = True

    workflow_template, template_created = WorkflowTemplate.objects.get_or_create(
        code=SAMPLE_ACCESSION_REFERENCE_OPERATION_CODE,
        defaults={
            "name": "Sample accession",
            "description": "Canonical sample accession reference workflow topology.",
            "purpose": "Reference accessioning workflow",
            "is_active": True,
        },
    )
    created = created or template_created
    workflow_version = (
        workflow_template.versions.filter(
            status=WorkflowTemplateVersion.Status.PUBLISHED
        )
        .order_by("-version_number")
        .first()
    )
    if workflow_version is None:
        workflow_version = _create_sample_accession_workflow_version(
            template=workflow_template,
            form_package_version=form_package_version,
        )
        created = True

    operation_definition, definition_created = (
        OperationDefinition.objects.get_or_create(
            code=SAMPLE_ACCESSION_REFERENCE_OPERATION_CODE,
            defaults={
                "name": "Sample accession",
                "description": "Canonical sample accession reference operation.",
                "purpose": "Reference accessioning operation",
                "module_scope": OperationDefinition.ModuleScope.LIMS,
                "is_active": True,
            },
        )
    )
    created = created or definition_created
    operation_version = (
        operation_definition.versions.filter(status=OperationVersion.Status.PUBLISHED)
        .order_by("-version_number")
        .first()
    )
    if operation_version is None:
        operation_version = _create_sample_accession_operation_version(
            definition=operation_definition,
            workflow_version=workflow_version,
        )
        created = True

    bundle = SampleAccessionReferenceBundle(
        form_package=form_package,
        form_package_version=form_package_version,
        workflow_template=workflow_template,
        workflow_version=workflow_version,
        operation_definition=operation_definition,
        operation_version=operation_version,
        created=created,
    )
    _assert_sample_accession_reference_bundle_invariants(bundle)
    return bundle


def _sample_accession_operation_version() -> OperationVersion:
    bundle = provision_sample_accession_reference_bundle()
    return bundle.operation_version


def _task_for_node_key(tasks: list[TaskRun], node_key: str) -> TaskRun:
    for task in tasks:
        if task.node_template.node_key == node_key:
            return task
    raise ReferenceOperationProvisionError(
        "workflow_task_not_found", [{"field": "node_key", "detail": node_key}]
    )


def _storage_reference_from_context(receipt_context: dict[str, object] | None) -> str:
    storage = (receipt_context or {}).get("storage")
    if not isinstance(storage, dict):
        return ""
    explicit_reference = str(
        storage.get("storage_reference") or storage.get("reference") or ""
    ).strip()
    if explicit_reference:
        return explicit_reference
    parts = [
        str(storage.get("location") or "").strip(),
        str(storage.get("container") or storage.get("box") or "").strip(),
        str(storage.get("position") or "").strip(),
    ]
    return " / ".join(part for part in parts if part)


def _source_reference_for_single_receive(
    *,
    sample_identifier: str,
    barcode: str,
    external_identifier: str,
) -> str:
    for candidate in (
        sample_identifier.strip(),
        barcode.strip(),
        external_identifier.strip(),
    ):
        if candidate:
            return candidate
    return ""


def _drive_sample_accession_runtime(
    *,
    source_mode: str,
    source_reference: str,
    initiated_by: str,
    subject_identifier: str,
    external_identifier: str,
    intake_payload: dict[str, object],
    qc_payload: dict[str, object],
    storage_payload: dict[str, object] | None = None,
    context: dict[str, object] | None = None,
    biospecimen: Biospecimen | None = None,
    manifest: AccessioningManifest | None = None,
    manifest_item: AccessioningManifestItem | None = None,
) -> SampleAccessionAdapterResult:
    operation_version = _sample_accession_operation_version()
    started = start_operation_run(
        operation_version,
        initiated_by=initiated_by,
        subject_identifier=subject_identifier,
        external_identifier=external_identifier,
        source_mode=source_mode,
        source_reference=source_reference,
        biospecimen=biospecimen,
        manifest=manifest,
        manifest_item=manifest_item,
        context=context or {},
    )
    intake_task = _task_for_node_key(started.created_tasks, "intake_capture")
    intake_result = submit_task_run(
        intake_task,
        payload=intake_payload,
        submitted_by=initiated_by,
    )
    qc_task = _task_for_node_key(intake_result.created_tasks, "qc_decision")
    qc_submit_result = submit_task_run(
        qc_task,
        payload=qc_payload,
        submitted_by=initiated_by,
    )
    if qc_task.requires_approval:
        qc_transition_result = approve_task_run(
            qc_task,
            outcome=ApprovalRecord.Outcome.APPROVED,
            approved_by=initiated_by,
            approver_role="transitional_adapter",
            meaning="Transitional receiving adapter finalized the QC decision.",
        )
    else:
        qc_transition_result = qc_submit_result
    if (
        str(qc_payload.get("qc_decision") or "").strip().lower()
        != QCResult.Decision.REJECT
    ):
        storage_task = _task_for_node_key(
            qc_transition_result.created_tasks, "storage_logging"
        )
        submit_task_run(
            storage_task,
            payload=storage_payload or {},
            submitted_by=initiated_by,
        )
    operation_run = OperationRun.objects.get(id=started.operation_run.id)
    qc_result = (
        QCResult.objects.select_related("discrepancy")
        .filter(operation_run=operation_run)
        .order_by("-reviewed_at", "-created_at")
        .first()
    )
    return SampleAccessionAdapterResult(
        operation_run=operation_run,
        qc_result=qc_result,
        discrepancy=(
            qc_result.discrepancy if qc_result and qc_result.discrepancy_id else None
        ),
        biospecimen=biospecimen,
        manifest_item=manifest_item,
    )


def adapt_single_receive_to_sample_accession(
    *,
    sample_type: BiospecimenType,
    study,
    site,
    lab,
    subject_identifier: str,
    external_identifier: str,
    quantity: Decimal,
    quantity_unit: str,
    metadata: dict[str, object],
    received_by: str,
    sample_identifier: str = "",
    barcode: str = "",
    scan_value: str = "",
    notes: str = "",
    receipt_context: dict[str, object] | None = None,
    received_at=None,
    source_mode: str = OperationRun.SourceMode.SINGLE,
    source_reference: str = "",
) -> SampleAccessionAdapterResult:
    qc = (receipt_context or {}).get("qc") if isinstance(receipt_context, dict) else {}
    if not isinstance(qc, dict):
        qc = {}
    qc_decision = (
        str(qc.get("decision") or QCResult.Decision.ACCEPT).strip().lower()
        or QCResult.Decision.ACCEPT
    )
    if qc_decision not in QCResult.Decision.values:
        qc_decision = QCResult.Decision.ACCEPT
    normalized_metadata = _validate_sample_type_metadata(sample_type, metadata)
    if scan_value and barcode and scan_value.strip() != barcode.strip():
        raise AccessioningError("scan_mismatch")

    specimen = None
    event = None
    if qc_decision != QCResult.Decision.REJECT:
        specimen, event = receive_single_biospecimen(
            sample_type=sample_type,
            study=study,
            site=site,
            lab=lab,
            subject_identifier=subject_identifier,
            external_identifier=external_identifier,
            quantity=quantity,
            quantity_unit=quantity_unit,
            metadata=normalized_metadata,
            received_by=received_by,
            sample_identifier=sample_identifier,
            barcode=barcode,
            scan_value=scan_value,
            notes=notes,
            receipt_context=receipt_context,
            received_at=received_at,
        )

    resolved_source_reference = (
        source_reference.strip()
        or _source_reference_for_single_receive(
            sample_identifier=(
                specimen.sample_identifier if specimen else sample_identifier
            ),
            barcode=specimen.barcode if specimen else barcode,
            external_identifier=external_identifier,
        )
    )
    intake_payload = {
        "subject_identifier": subject_identifier.strip(),
        "external_identifier": external_identifier.strip(),
        "sample_identifier": (
            specimen.sample_identifier if specimen else sample_identifier.strip()
        ),
        "barcode": specimen.barcode if specimen else barcode.strip(),
        "received_at": received_at.isoformat() if received_at else None,
        "quantity": str(quantity),
        "quantity_unit": quantity_unit.strip(),
        "brought_by": str((receipt_context or {}).get("brought_by") or "").strip(),
        "source_reference": resolved_source_reference,
    }
    qc_payload = {
        "qc_decision": qc_decision,
        "notes": str(qc.get("notes") or notes or "").strip(),
        "rejection_code": str(qc.get("rejection_code") or "").strip(),
        "reason": str(qc.get("reason") or qc.get("notes") or notes or "").strip(),
    }
    storage_reference = _storage_reference_from_context(receipt_context)
    storage_payload = {
        "storage_reference": storage_reference,
        "storage_notes": (
            str(
                ((receipt_context or {}).get("storage") or {}).get("notes") or ""
            ).strip()
            if isinstance((receipt_context or {}).get("storage"), dict)
            else ""
        ),
    }
    context = {
        "adapter_kind": "single_receive",
        "sample_type_id": str(sample_type.id),
        "notes": notes,
        "metadata": normalized_metadata,
        "receipt_context": dict(receipt_context or {}),
        "receiving_event_id": str(event.id) if event else None,
    }
    result = _drive_sample_accession_runtime(
        source_mode=source_mode,
        source_reference=resolved_source_reference,
        initiated_by=received_by,
        subject_identifier=subject_identifier.strip(),
        external_identifier=external_identifier.strip(),
        intake_payload=intake_payload,
        qc_payload=qc_payload,
        storage_payload=storage_payload,
        context=context,
        biospecimen=specimen,
    )
    return SampleAccessionAdapterResult(
        operation_run=result.operation_run,
        qc_result=result.qc_result,
        biospecimen=specimen,
        event=event,
        discrepancy=result.discrepancy,
    )


def adapt_manifest_item_receive_to_sample_accession(
    item: AccessioningManifestItem,
    *,
    received_by: str,
    scan_value: str = "",
    notes: str = "",
    metadata: dict[str, object] | None = None,
    receipt_context: dict[str, object] | None = None,
    received_at=None,
    source_mode: str = OperationRun.SourceMode.BATCH,
    source_reference: str = "",
) -> SampleAccessionAdapterResult:
    if item.status == AccessioningManifestItem.Status.RECEIVED:
        raise AccessioningError("item_already_received")
    manifest = item.manifest
    if manifest.status == AccessioningManifest.Status.DRAFT:
        raise AccessioningError("manifest_not_submitted")
    candidate_values = {
        value.strip()
        for value in [item.expected_sample_identifier, item.expected_barcode]
        if isinstance(value, str) and value.strip()
    }
    if scan_value and candidate_values and scan_value.strip() not in candidate_values:
        raise AccessioningError("scan_mismatch")
    qc = (receipt_context or {}).get("qc") if isinstance(receipt_context, dict) else {}
    if not isinstance(qc, dict):
        qc = {}
    qc_decision = (
        str(qc.get("decision") or QCResult.Decision.ACCEPT).strip().lower()
        or QCResult.Decision.ACCEPT
    )
    if qc_decision not in QCResult.Decision.values:
        qc_decision = QCResult.Decision.ACCEPT
    payload_metadata = dict(item.metadata or {})
    payload_metadata.update(metadata or {})
    normalized_metadata = _validate_sample_type_metadata(
        item.manifest.sample_type, payload_metadata
    )

    updated_item = item
    event = None
    specimen = item.biospecimen
    if qc_decision != QCResult.Decision.REJECT:
        updated_item, event = receive_manifest_item(
            item,
            received_by=received_by,
            scan_value=scan_value,
            notes=notes,
            metadata=normalized_metadata,
            receipt_context=receipt_context,
            received_at=received_at,
        )
        specimen = updated_item.biospecimen

    resolved_source_reference = (
        source_reference.strip()
        or manifest.source_reference
        or manifest.manifest_identifier
    )
    intake_payload = {
        "subject_identifier": updated_item.expected_subject_identifier,
        "external_identifier": str(
            (normalized_metadata or {}).get("external_id") or ""
        ).strip(),
        "sample_identifier": (
            specimen.sample_identifier
            if specimen
            else updated_item.expected_sample_identifier
        ),
        "barcode": specimen.barcode if specimen else updated_item.expected_barcode,
        "received_at": received_at.isoformat() if received_at else None,
        "quantity": str(updated_item.quantity),
        "quantity_unit": updated_item.quantity_unit,
        "brought_by": str((receipt_context or {}).get("brought_by") or "").strip(),
        "source_reference": resolved_source_reference,
    }
    qc_payload = {
        "qc_decision": qc_decision,
        "notes": str(qc.get("notes") or notes or "").strip(),
        "rejection_code": str(qc.get("rejection_code") or "").strip(),
        "reason": str(qc.get("reason") or qc.get("notes") or notes or "").strip(),
    }
    storage_reference = _storage_reference_from_context(receipt_context)
    storage_payload = {
        "storage_reference": storage_reference,
        "storage_notes": (
            str(
                ((receipt_context or {}).get("storage") or {}).get("notes") or ""
            ).strip()
            if isinstance((receipt_context or {}).get("storage"), dict)
            else ""
        ),
    }
    context = {
        "adapter_kind": "manifest_item_receive",
        "manifest_id": str(manifest.id),
        "manifest_item_id": str(updated_item.id),
        "notes": notes,
        "metadata": normalized_metadata,
        "receipt_context": dict(receipt_context or {}),
        "receiving_event_id": str(event.id) if event else None,
    }
    result = _drive_sample_accession_runtime(
        source_mode=source_mode,
        source_reference=resolved_source_reference,
        initiated_by=received_by,
        subject_identifier=updated_item.expected_subject_identifier,
        external_identifier=str(
            (normalized_metadata or {}).get("external_id") or ""
        ).strip(),
        intake_payload=intake_payload,
        qc_payload=qc_payload,
        storage_payload=storage_payload,
        context=context,
        biospecimen=specimen,
        manifest=manifest,
        manifest_item=updated_item,
    )
    return SampleAccessionAdapterResult(
        operation_run=result.operation_run,
        qc_result=result.qc_result,
        biospecimen=specimen,
        event=event,
        manifest_item=updated_item,
        discrepancy=result.discrepancy,
    )


def _bool_from_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    raise ValueError("invalid_boolean")


def _normalize_field_value(field: MetadataSchemaField, value: object) -> object:
    if field.field_type in {
        MetadataFieldDefinition.FieldType.TEXT,
        MetadataFieldDefinition.FieldType.LONG_TEXT,
        MetadataFieldDefinition.FieldType.CHOICE,
    }:
        if not isinstance(value, str):
            raise ValueError("expected_string")
        return value.strip()

    if field.field_type == MetadataFieldDefinition.FieldType.INTEGER:
        if isinstance(value, bool):
            raise ValueError("expected_integer")
        return int(value)

    if field.field_type == MetadataFieldDefinition.FieldType.DECIMAL:
        if isinstance(value, bool):
            raise ValueError("expected_decimal")
        return str(Decimal(str(value)))

    if field.field_type == MetadataFieldDefinition.FieldType.BOOLEAN:
        return _bool_from_value(value)

    if field.field_type == MetadataFieldDefinition.FieldType.DATE:
        if not isinstance(value, str):
            raise ValueError("expected_iso_date")
        return date.fromisoformat(value).isoformat()

    if field.field_type == MetadataFieldDefinition.FieldType.DATETIME:
        if not isinstance(value, str):
            raise ValueError("expected_iso_datetime")
        return datetime.fromisoformat(value).isoformat()

    if field.field_type == MetadataFieldDefinition.FieldType.MULTI_CHOICE:
        if not isinstance(value, list):
            raise ValueError("expected_list")
        if not all(isinstance(item, str) for item in value):
            raise ValueError("expected_list_of_strings")
        return [item.strip() for item in value]

    raise ValueError("unsupported_field_type")


def _validate_vocabulary(
    field: MetadataSchemaField, normalized_value: object
) -> str | None:
    if not field.vocabulary_id:
        return None
    allowed_values = set(
        MetadataVocabularyItem.objects.filter(
            vocabulary_id=field.vocabulary_id, is_active=True
        ).values_list("value", flat=True)
    )
    if field.field_type == MetadataFieldDefinition.FieldType.MULTI_CHOICE:
        invalid = [item for item in normalized_value if item not in allowed_values]
        if invalid:
            return "invalid_choice"
        return None
    if normalized_value not in allowed_values:
        return "invalid_choice"
    return None


def get_default_metadata_vocabulary_domain() -> MetadataVocabularyDomain:
    domain, _ = MetadataVocabularyDomain.objects.get_or_create(
        code=DEFAULT_METADATA_VOCABULARY_DOMAIN_CODE,
        defaults={
            "name": "General",
            "description": "Fallback domain for vocabularies created before functional categorization was introduced.",
            "is_active": True,
        },
    )
    return domain


@transaction.atomic
def provision_default_metadata_vocabularies() -> dict[str, object]:
    created_domains = 0
    created_vocabularies = 0
    created_items = 0

    for pack in DEFAULT_METADATA_VOCABULARY_PACK:
        domain_payload = pack["domain"]
        domain, domain_created = MetadataVocabularyDomain.objects.get_or_create(
            code=domain_payload["code"],
            defaults={
                "name": domain_payload["name"],
                "description": domain_payload["description"],
                "is_active": True,
            },
        )
        if not domain_created:
            changed = False
            for attr in ("name", "description"):
                value = domain_payload[attr]
                if getattr(domain, attr) != value:
                    setattr(domain, attr, value)
                    changed = True
            if not domain.is_active:
                domain.is_active = True
                changed = True
            if changed:
                domain.save(
                    update_fields=["name", "description", "is_active", "updated_at"]
                )
        else:
            created_domains += 1

        for vocabulary_payload in pack["vocabularies"]:
            vocabulary, vocabulary_created = MetadataVocabulary.objects.get_or_create(
                code=vocabulary_payload["code"],
                defaults={
                    "domain": domain,
                    "name": vocabulary_payload["name"],
                    "description": vocabulary_payload["description"],
                    "is_active": True,
                },
            )
            if not vocabulary_created:
                changed = False
                if vocabulary.domain_id != domain.id:
                    vocabulary.domain = domain
                    changed = True
                for attr in ("name", "description"):
                    value = vocabulary_payload[attr]
                    if getattr(vocabulary, attr) != value:
                        setattr(vocabulary, attr, value)
                        changed = True
                if not vocabulary.is_active:
                    vocabulary.is_active = True
                    changed = True
                if changed:
                    vocabulary.save(
                        update_fields=[
                            "domain",
                            "name",
                            "description",
                            "is_active",
                            "updated_at",
                        ]
                    )
            else:
                created_vocabularies += 1

            for sort_order, (value, label) in enumerate(
                vocabulary_payload["items"], start=1
            ):
                _, item_created = MetadataVocabularyItem.objects.update_or_create(
                    vocabulary=vocabulary,
                    value=value,
                    defaults={
                        "label": label,
                        "sort_order": sort_order,
                        "is_active": True,
                    },
                )
                if item_created:
                    created_items += 1

    return {
        "created_domains": created_domains,
        "created_vocabularies": created_vocabularies,
        "created_items": created_items,
    }


def _compare_min_max(
    field: MetadataSchemaField, normalized_value: object, rules: dict[str, object]
) -> str | None:
    if field.field_type in {
        MetadataFieldDefinition.FieldType.TEXT,
        MetadataFieldDefinition.FieldType.LONG_TEXT,
    }:
        min_length = rules.get("min_length")
        max_length = rules.get("max_length")
        if min_length is not None and len(normalized_value) < int(min_length):
            return "min_length"
        if max_length is not None and len(normalized_value) > int(max_length):
            return "max_length"
        return None

    if field.field_type == MetadataFieldDefinition.FieldType.MULTI_CHOICE:
        min_items = rules.get("min_items")
        max_items = rules.get("max_items")
        if min_items is not None and len(normalized_value) < int(min_items):
            return "min_items"
        if max_items is not None and len(normalized_value) > int(max_items):
            return "max_items"
        return None

    if field.field_type in {
        MetadataFieldDefinition.FieldType.INTEGER,
        MetadataFieldDefinition.FieldType.DECIMAL,
    }:
        numeric_value = Decimal(str(normalized_value))
        if rules.get("min") is not None and numeric_value < Decimal(str(rules["min"])):
            return "min"
        if rules.get("max") is not None and numeric_value > Decimal(str(rules["max"])):
            return "max"
        return None

    return None


def validate_metadata_payload(
    schema_version: MetadataSchemaVersion,
    payload: dict[str, object],
) -> MetadataValidationResult:
    errors: list[dict[str, str]] = []
    normalized_data: dict[str, object] = {}
    schema_fields = list(
        schema_version.fields.select_related("vocabulary").order_by(
            "position", "field_key"
        )
    )

    for schema_field in schema_fields:
        is_active = _condition_matches(dict(schema_field.condition or {}), payload)
        if not is_active:
            continue

        raw_value = payload.get(schema_field.field_key)
        if raw_value in (None, "") or raw_value == []:
            if schema_field.default_value is not None:
                raw_value = schema_field.default_value
            elif schema_field.required:
                errors.append({"field": schema_field.field_key, "code": "required"})
                continue
            else:
                continue

        try:
            normalized_value = _normalize_field_value(schema_field, raw_value)
        except (TypeError, ValueError):
            errors.append({"field": schema_field.field_key, "code": "invalid_type"})
            continue

        vocabulary_error = _validate_vocabulary(schema_field, normalized_value)
        if vocabulary_error:
            errors.append({"field": schema_field.field_key, "code": vocabulary_error})
            continue

        range_error = _compare_min_max(
            schema_field, normalized_value, dict(schema_field.validation_rules or {})
        )
        if range_error:
            errors.append({"field": schema_field.field_key, "code": range_error})
            continue

        normalized_data[schema_field.field_key] = normalized_value

    return MetadataValidationResult(
        valid=not errors, errors=errors, normalized_data=normalized_data
    )


def resolve_schema_version_for_binding(
    *, target_type: str, target_key: str
) -> MetadataSchemaVersion | None:
    binding = (
        MetadataSchemaBinding.objects.select_related(
            "schema_version", "schema_version__schema"
        )
        .filter(target_type=target_type, target_key=target_key, is_active=True)
        .first()
    )
    if not binding:
        return None
    return binding.schema_version


def validate_workflow_template_version(
    workflow_version: WorkflowTemplateVersion,
) -> WorkflowTemplateValidationResult:
    nodes = list(
        workflow_version.nodes.prefetch_related(
            "step_bindings__form_package_version__package",
            "step_bindings__form_package_version__sections",
            "step_bindings__form_package_version__item_groups",
            "step_bindings__form_package_version__items",
        ).order_by("position", "node_key")
    )
    edges = list(
        workflow_version.edges.select_related("source_node", "target_node").order_by(
            "priority", "source_node__node_key"
        )
    )
    errors: list[dict[str, str]] = []

    if not nodes:
        errors.append({"field": "nodes", "code": "version_requires_nodes"})
    if not edges:
        errors.append({"field": "edges", "code": "version_requires_edges"})

    node_by_id = {node.id: node for node in nodes}
    start_nodes = [
        node for node in nodes if node.node_type == WorkflowNodeTemplate.NodeType.START
    ]
    end_nodes = [
        node for node in nodes if node.node_type == WorkflowNodeTemplate.NodeType.END
    ]
    if len(start_nodes) != 1:
        errors.append({"field": "nodes", "code": "requires_exactly_one_start"})
    if not end_nodes:
        errors.append({"field": "nodes", "code": "requires_end_node"})

    incoming: dict[str, list[WorkflowEdgeTemplate]] = {
        str(node.id): [] for node in nodes
    }
    outgoing: dict[str, list[WorkflowEdgeTemplate]] = {
        str(node.id): [] for node in nodes
    }
    for edge in edges:
        source_key = str(edge.source_node_id)
        target_key = str(edge.target_node_id)
        if source_key not in outgoing or target_key not in incoming:
            errors.append({"field": "edges", "code": "edge_references_unknown_node"})
            continue
        outgoing[source_key].append(edge)
        incoming[target_key].append(edge)

    branch_types = {
        WorkflowNodeTemplate.NodeType.IF,
        WorkflowNodeTemplate.NodeType.SWITCH,
        WorkflowNodeTemplate.NodeType.SPLIT,
        WorkflowNodeTemplate.NodeType.SPLIT_FIRST,
    }
    linear_types = {
        WorkflowNodeTemplate.NodeType.START,
        WorkflowNodeTemplate.NodeType.START_HANDLE,
        WorkflowNodeTemplate.NodeType.VIEW,
        WorkflowNodeTemplate.NodeType.FUNCTION,
        WorkflowNodeTemplate.NodeType.HANDLE,
        WorkflowNodeTemplate.NodeType.JOIN,
    }
    available_condition_item_keys: set[str] = set()

    for node in nodes:
        node_id = str(node.id)
        inbound = incoming[node_id]
        outbound = outgoing[node_id]
        if node.node_type == WorkflowNodeTemplate.NodeType.START:
            if inbound:
                errors.append(
                    {
                        "field": f"nodes.{node.node_key}",
                        "code": "start_cannot_have_incoming_edges",
                    }
                )
            if len(outbound) != 1:
                errors.append(
                    {
                        "field": f"nodes.{node.node_key}",
                        "code": "start_requires_one_outgoing_edge",
                    }
                )
        elif node.node_type == WorkflowNodeTemplate.NodeType.END:
            if outbound:
                errors.append(
                    {
                        "field": f"nodes.{node.node_key}",
                        "code": "end_cannot_have_outgoing_edges",
                    }
                )
            if not inbound:
                errors.append(
                    {
                        "field": f"nodes.{node.node_key}",
                        "code": "end_requires_incoming_edge",
                    }
                )
        else:
            if not inbound:
                errors.append(
                    {
                        "field": f"nodes.{node.node_key}",
                        "code": "node_requires_incoming_edge",
                    }
                )
            if node.node_type in branch_types and len(outbound) < 2:
                errors.append(
                    {
                        "field": f"nodes.{node.node_key}",
                        "code": "branch_node_requires_multiple_outgoing_edges",
                    }
                )
            if node.node_type in linear_types and len(outbound) != 1:
                errors.append(
                    {
                        "field": f"nodes.{node.node_key}",
                        "code": "linear_node_requires_one_outgoing_edge",
                    }
                )

        for binding in node.step_bindings.all():
            package_version = binding.form_package_version
            if package_version is None:
                errors.append(
                    {
                        "field": f"bindings.{node.node_key}",
                        "code": "form_package_version_required",
                    }
                )
                continue
            package_section_keys = {
                item.section_key for item in package_version.sections.all()
            }
            package_group_keys = {
                item.group_key for item in package_version.item_groups.all()
            }
            package_item_keys = {item.item_key for item in package_version.items.all()}
            if binding.binding_type == WorkflowStepBinding.BindingType.SECTION_SET:
                missing = sorted(set(binding.section_keys or []) - package_section_keys)
                if missing:
                    errors.append(
                        {
                            "field": f"bindings.{node.node_key}",
                            "code": "section_keys_not_found",
                            "detail": ",".join(missing),
                        }
                    )
                else:
                    selected_sections = set(binding.section_keys or [])
                    available_condition_item_keys.update(
                        item.item_key
                        for item in package_version.items.all()
                        if item.section.section_key in selected_sections
                    )
            elif binding.binding_type == WorkflowStepBinding.BindingType.GROUP_SET:
                missing = sorted(
                    set(binding.item_group_keys or []) - package_group_keys
                )
                if missing:
                    errors.append(
                        {
                            "field": f"bindings.{node.node_key}",
                            "code": "item_group_keys_not_found",
                            "detail": ",".join(missing),
                        }
                    )
                else:
                    selected_groups = set(binding.item_group_keys or [])
                    available_condition_item_keys.update(
                        item.item_key
                        for item in package_version.items.all()
                        if item.item_group_id
                        and item.item_group.group_key in selected_groups
                    )
            elif binding.binding_type == WorkflowStepBinding.BindingType.ITEM_SET:
                missing = sorted(set(binding.item_keys or []) - package_item_keys)
                if missing:
                    errors.append(
                        {
                            "field": f"bindings.{node.node_key}",
                            "code": "item_keys_not_found",
                            "detail": ",".join(missing),
                        }
                    )
                else:
                    available_condition_item_keys.update(binding.item_keys or [])
            else:
                available_condition_item_keys.update(package_item_keys)

    for edge in edges:
        condition_item_key = (
            str(edge.condition.get("item_key") or "").strip()
            if isinstance(edge.condition, dict)
            else ""
        )
        if (
            condition_item_key
            and condition_item_key not in available_condition_item_keys
        ):
            errors.append(
                {
                    "field": f"edges.{edge.source_node.node_key}->{edge.target_node.node_key}",
                    "code": "condition_item_key_not_found",
                    "detail": condition_item_key,
                }
            )

    if start_nodes:
        visited: set[str] = set()
        pending = [str(start_nodes[0].id)]
        while pending:
            current = pending.pop()
            if current in visited:
                continue
            visited.add(current)
            pending.extend(str(edge.target_node_id) for edge in outgoing[current])
        unreachable = [node.node_key for node in nodes if str(node.id) not in visited]
        if unreachable:
            errors.append(
                {
                    "field": "nodes",
                    "code": "unreachable_nodes",
                    "detail": ",".join(sorted(unreachable)),
                }
            )

    compiled_definition = {
        "template_id": str(workflow_version.template_id),
        "workflow_version_id": str(workflow_version.id),
        "version_number": workflow_version.version_number,
        "nodes": [
            {
                "id": str(node.id),
                "node_key": node.node_key,
                "node_type": node.node_type,
                "title": node.title,
                "summary": node.summary,
                "position": node.position,
                "assignment_role": node.assignment_role,
                "permission_key": node.permission_key,
                "requires_approval": node.requires_approval,
                "approval_role": node.approval_role,
                "assignment": {
                    "role": node.assignment_role or None,
                },
                "permission": {
                    "key": node.permission_key or None,
                },
                "approval": {
                    "required": node.requires_approval,
                    "role": node.approval_role or None,
                },
                "config": dict(node.config or {}),
                "bindings": [
                    {
                        "id": str(binding.id),
                        "form_package_version_id": (
                            str(binding.form_package_version_id)
                            if binding.form_package_version_id
                            else None
                        ),
                        "form_package_id": (
                            str(binding.form_package_version.package_id)
                            if binding.form_package_version_id
                            else None
                        ),
                        "form_package_code": (
                            binding.form_package_version.package.code
                            if binding.form_package_version_id
                            else ""
                        ),
                        "form_package_name": (
                            binding.form_package_version.package.name
                            if binding.form_package_version_id
                            else ""
                        ),
                        "version_number": (
                            binding.form_package_version.version_number
                            if binding.form_package_version_id
                            else None
                        ),
                        "binding_type": binding.binding_type,
                        "section_keys": list(binding.section_keys or []),
                        "item_group_keys": list(binding.item_group_keys or []),
                        "item_keys": list(binding.item_keys or []),
                        "is_required": binding.is_required,
                    }
                    for binding in node.step_bindings.all()
                ],
            }
            for node in nodes
        ],
        "edges": [
            {
                "id": str(edge.id),
                "source_node_key": edge.source_node.node_key,
                "target_node_key": edge.target_node.node_key,
                "priority": edge.priority,
                "condition": dict(edge.condition or {}),
            }
            for edge in edges
        ],
    }
    return WorkflowTemplateValidationResult(
        valid=not errors, errors=errors, compiled_definition=compiled_definition
    )


def validate_operation_version(
    operation_version: OperationVersion,
) -> OperationVersionValidationResult:
    errors: list[dict[str, str]] = []
    workflow_version = operation_version.workflow_version
    if workflow_version.status != WorkflowTemplateVersion.Status.PUBLISHED:
        errors.append(
            {"field": "workflow_version", "code": "workflow_version_must_be_published"}
        )
    if not workflow_version.compiled_definition:
        errors.append(
            {"field": "workflow_version", "code": "workflow_version_must_be_compiled"}
        )
    if workflow_version.template.code != operation_version.definition.code:
        errors.append(
            {"field": "workflow_version", "code": "workflow_template_code_mismatch"}
        )
    return OperationVersionValidationResult(valid=not errors, errors=errors)


def _evaluate_workflow_condition(
    condition: dict[str, object], payload: dict[str, object]
) -> bool:
    if not condition:
        return True
    field = str(condition.get("item_key") or condition.get("field") or "").strip()
    if not field:
        return True
    operator = str(condition.get("operator") or "equals").strip()
    actual = payload.get(field)
    if operator == "equals":
        return actual == condition.get("value")
    if operator == "not_equals":
        return actual != condition.get("value")
    if operator == "in":
        expected = condition.get("value") or []
        return actual in expected if isinstance(expected, list) else False
    if operator == "exists":
        return actual not in (None, "", [])
    if operator == "truthy":
        return bool(actual)
    return False


def _select_outgoing_edges(
    node: WorkflowNodeTemplate, payload: dict[str, object]
) -> list[WorkflowEdgeTemplate]:
    outgoing_edges = list(
        node.outgoing_edges.all().order_by("priority", "target_node__node_key")
    )
    matched_edges = [
        edge
        for edge in outgoing_edges
        if _evaluate_workflow_condition(dict(edge.condition or {}), payload)
    ]
    if node.node_type in {
        WorkflowNodeTemplate.NodeType.IF,
        WorkflowNodeTemplate.NodeType.SWITCH,
        WorkflowNodeTemplate.NodeType.SPLIT_FIRST,
    }:
        return matched_edges[:1]
    if node.node_type == WorkflowNodeTemplate.NodeType.SPLIT:
        return matched_edges
    return outgoing_edges[:1]


def _create_task_run_for_node(
    operation_run: OperationRun, node: WorkflowNodeTemplate
) -> TaskRun:
    return TaskRun.objects.create(
        operation_run=operation_run,
        node_template=node,
        status=TaskRun.Status.OPEN,
        assignment_role=node.assignment_role,
        permission_key=node.permission_key,
        requires_approval=node.requires_approval,
        approval_role=node.approval_role,
        input_context=dict(node.config or {}),
    )


def _complete_operation_run(
    operation_run: OperationRun,
    *,
    payload: dict[str, object],
    terminal_node: WorkflowNodeTemplate,
) -> None:
    outcome = str(payload.get("qc_decision") or "").strip().lower()
    if outcome == "reject" or "reject" in terminal_node.node_key:
        operation_run.status = OperationRun.Status.REJECTED
        operation_run.outcome = "rejected"
    else:
        operation_run.status = OperationRun.Status.COMPLETED
        operation_run.outcome = outcome or terminal_node.node_key
    operation_run.completed_at = timezone.now()
    operation_run.save(
        update_fields=["status", "outcome", "completed_at", "updated_at"]
    )


def _advance_task_run(task_run: TaskRun, payload: dict[str, object]) -> list[TaskRun]:
    operation_run = task_run.operation_run
    node = task_run.node_template
    created_tasks: list[TaskRun] = []
    for edge in _select_outgoing_edges(node, payload):
        target_node = edge.target_node
        if target_node.node_type == WorkflowNodeTemplate.NodeType.END:
            _complete_operation_run(
                operation_run, payload=payload, terminal_node=target_node
            )
            continue
        created_tasks.append(_create_task_run_for_node(operation_run, target_node))
    return created_tasks


def _record_qc_result(
    task_run: TaskRun,
    *,
    payload: dict[str, object],
    submission: SubmissionRecord | None,
    recorded_by: str,
) -> QCResult | None:
    if task_run.node_template.node_key != "qc_decision":
        return None
    decision = str(payload.get("qc_decision") or "").strip().lower()
    if decision not in QCResult.Decision.values:
        return None
    existing = (
        QCResult.objects.filter(task_run=task_run).select_related("discrepancy").first()
    )
    discrepancy = None
    rejection_code = ""
    if decision == QCResult.Decision.REJECT:
        rejection_code = str(
            payload.get("rejection_code") or ReceivingDiscrepancy.Code.OTHER
        ).strip()
        if rejection_code not in ReceivingDiscrepancy.Code.values:
            rejection_code = ReceivingDiscrepancy.Code.OTHER
        discrepancy = existing.discrepancy if existing else None
        if discrepancy is None:
            discrepancy = create_receiving_discrepancy(
                code=rejection_code,
                recorded_by=recorded_by,
                manifest=task_run.operation_run.manifest,
                manifest_item=task_run.operation_run.manifest_item,
                biospecimen=task_run.operation_run.biospecimen,
                notes=str(payload.get("reason") or payload.get("notes") or "").strip(),
                expected_data={},
                actual_data=dict(payload or {}),
            )
    qc_result, _ = QCResult.objects.update_or_create(
        task_run=task_run,
        defaults={
            "operation_run": task_run.operation_run,
            "submission_record": submission,
            "discrepancy": discrepancy,
            "decision": decision,
            "notes": str(payload.get("notes") or payload.get("reason") or "").strip(),
            "rejection_code": rejection_code,
            "recorded_by": recorded_by,
            "reviewed_at": timezone.now(),
        },
    )
    MaterialUsageRecord.objects.update_or_create(
        operation_run=task_run.operation_run,
        task_run=task_run,
        action="rejected" if decision == QCResult.Decision.REJECT else "accepted",
        defaults={
            "biospecimen": task_run.operation_run.biospecimen,
            "manifest": task_run.operation_run.manifest,
            "manifest_item": task_run.operation_run.manifest_item,
            "discrepancy": discrepancy,
            "details": {
                "decision": decision,
                "reason": payload.get("reason") or payload.get("notes") or "",
                "rejection_code": rejection_code,
            },
        },
    )
    return qc_result


@transaction.atomic
def start_operation_run(
    operation_version: OperationVersion,
    *,
    initiated_by: str = "",
    subject_identifier: str = "",
    external_identifier: str = "",
    source_mode: str = OperationRun.SourceMode.SINGLE,
    source_reference: str = "",
    biospecimen: Biospecimen | None = None,
    manifest: AccessioningManifest | None = None,
    manifest_item: AccessioningManifestItem | None = None,
    context: dict[str, object] | None = None,
) -> OperationTaskTransitionResult:
    if operation_version.status != OperationVersion.Status.PUBLISHED:
        raise ValueError("operation_version_must_be_published")
    workflow_version = WorkflowTemplateVersion.objects.prefetch_related(
        "nodes__outgoing_edges__target_node",
        "edges__source_node",
        "edges__target_node",
    ).get(id=operation_version.workflow_version_id)
    operation_run = OperationRun.objects.create(
        operation_version=operation_version,
        workflow_version=workflow_version,
        status=OperationRun.Status.ACTIVE,
        source_mode=source_mode,
        source_reference=source_reference,
        subject_identifier=subject_identifier,
        external_identifier=external_identifier,
        initiated_by=initiated_by,
        biospecimen=biospecimen,
        manifest=manifest,
        manifest_item=manifest_item,
        context=dict(context or {}),
    )
    if biospecimen or manifest or manifest_item:
        MaterialUsageRecord.objects.create(
            operation_run=operation_run,
            biospecimen=biospecimen,
            manifest=manifest,
            manifest_item=manifest_item,
            action="bound",
            details={"source_mode": source_mode},
        )
    start_node = workflow_version.nodes.get(
        node_type=WorkflowNodeTemplate.NodeType.START
    )
    created_tasks: list[TaskRun] = []
    for edge in start_node.outgoing_edges.all().order_by(
        "priority", "target_node__node_key"
    ):
        if edge.target_node.node_type == WorkflowNodeTemplate.NodeType.END:
            _complete_operation_run(
                operation_run, payload={}, terminal_node=edge.target_node
            )
            continue
        created_tasks.append(_create_task_run_for_node(operation_run, edge.target_node))
    primary_task = (
        created_tasks[0]
        if created_tasks
        else TaskRun(
            operation_run=operation_run,
            node_template=start_node,
        )
    )
    return OperationTaskTransitionResult(
        task_run=primary_task, operation_run=operation_run, created_tasks=created_tasks
    )


@transaction.atomic
def submit_task_run(
    task_run: TaskRun,
    *,
    payload: dict[str, object],
    submitted_by: str = "",
    status: str = SubmissionRecord.Status.SUBMITTED,
) -> OperationTaskTransitionResult:
    latest_index = (
        task_run.submissions.order_by("-submission_index")
        .values_list("submission_index", flat=True)
        .first()
        or 0
    )
    submission = SubmissionRecord.objects.create(
        task_run=task_run,
        submission_index=latest_index + 1,
        status=status,
        payload=dict(payload or {}),
        submitted_by=submitted_by,
    )
    task_run.output_data = dict(payload or {})
    task_run.outcome = str(
        payload.get("qc_decision") or payload.get("outcome") or ""
    ).strip()
    if task_run.requires_approval:
        task_run.status = TaskRun.Status.AWAITING_APPROVAL
        task_run.save(update_fields=["status", "output_data", "outcome", "updated_at"])
        return OperationTaskTransitionResult(
            task_run=task_run,
            operation_run=task_run.operation_run,
            created_tasks=[],
            submission=submission,
        )
    task_run.status = TaskRun.Status.COMPLETED
    task_run.completed_at = timezone.now()
    task_run.save(
        update_fields=["status", "output_data", "outcome", "completed_at", "updated_at"]
    )
    _record_qc_result(
        task_run,
        payload=dict(payload or {}),
        submission=submission,
        recorded_by=submitted_by,
    )
    created_tasks = _advance_task_run(task_run, dict(payload or {}))
    if "storage_reference" in payload or "storage_slot" in payload:
        MaterialUsageRecord.objects.create(
            operation_run=task_run.operation_run,
            task_run=task_run,
            biospecimen=task_run.operation_run.biospecimen,
            manifest=task_run.operation_run.manifest,
            manifest_item=task_run.operation_run.manifest_item,
            action="stored",
            details={
                "storage_reference": payload.get("storage_reference")
                or payload.get("storage_slot")
                or ""
            },
        )
    return OperationTaskTransitionResult(
        task_run=task_run,
        operation_run=task_run.operation_run,
        created_tasks=created_tasks,
        submission=submission,
    )


@transaction.atomic
def approve_task_run(
    task_run: TaskRun,
    *,
    outcome: str,
    approved_by: str = "",
    approver_role: str = "",
    meaning: str = "",
    comments: str = "",
) -> OperationTaskTransitionResult:
    if task_run.status != TaskRun.Status.AWAITING_APPROVAL:
        raise ValueError("task_run_not_awaiting_approval")
    approval = ApprovalRecord.objects.create(
        operation_run=task_run.operation_run,
        task_run=task_run,
        outcome=outcome,
        approved_by=approved_by,
        approver_role=approver_role,
        meaning=meaning,
        comments=comments,
    )
    if outcome == ApprovalRecord.Outcome.REJECTED:
        task_run.status = TaskRun.Status.OPEN
        task_run.save(update_fields=["status", "updated_at"])
        return OperationTaskTransitionResult(
            task_run=task_run,
            operation_run=task_run.operation_run,
            created_tasks=[],
            approval=approval,
        )
    latest_submission = task_run.submissions.order_by("-submission_index").first()
    task_run.status = TaskRun.Status.COMPLETED
    task_run.completed_at = timezone.now()
    task_run.save(update_fields=["status", "completed_at", "updated_at"])
    payload = dict(latest_submission.payload if latest_submission else {})
    _record_qc_result(
        task_run,
        payload=payload,
        submission=latest_submission,
        recorded_by=approved_by,
    )
    created_tasks = _advance_task_run(task_run, payload)
    return OperationTaskTransitionResult(
        task_run=task_run,
        operation_run=task_run.operation_run,
        created_tasks=created_tasks,
        submission=latest_submission,
        approval=approval,
    )


ALLOWED_BIOSPECIMEN_TRANSITIONS = {
    Biospecimen.Status.REGISTERED: {
        Biospecimen.Status.RECEIVED,
        Biospecimen.Status.DISPOSED,
    },
    Biospecimen.Status.RECEIVED: {
        Biospecimen.Status.AVAILABLE,
        Biospecimen.Status.ALIQUOTED,
        Biospecimen.Status.POOLED,
        Biospecimen.Status.ARCHIVED,
        Biospecimen.Status.DISPOSED,
    },
    Biospecimen.Status.AVAILABLE: {
        Biospecimen.Status.ALIQUOTED,
        Biospecimen.Status.POOLED,
        Biospecimen.Status.CONSUMED,
        Biospecimen.Status.ARCHIVED,
        Biospecimen.Status.DISPOSED,
    },
    Biospecimen.Status.ALIQUOTED: {
        Biospecimen.Status.POOLED,
        Biospecimen.Status.CONSUMED,
        Biospecimen.Status.ARCHIVED,
        Biospecimen.Status.DISPOSED,
    },
    Biospecimen.Status.POOLED: {
        Biospecimen.Status.CONSUMED,
        Biospecimen.Status.ARCHIVED,
    },
    Biospecimen.Status.CONSUMED: {
        Biospecimen.Status.ARCHIVED,
    },
    Biospecimen.Status.ARCHIVED: {
        Biospecimen.Status.DISPOSED,
    },
    Biospecimen.Status.DISPOSED: set(),
}

ALLOWED_POOL_TRANSITIONS = {
    BiospecimenPool.Status.ASSEMBLED: {
        BiospecimenPool.Status.CONSUMED,
        BiospecimenPool.Status.ARCHIVED,
    },
    BiospecimenPool.Status.CONSUMED: {
        BiospecimenPool.Status.ARCHIVED,
    },
    BiospecimenPool.Status.ARCHIVED: set(),
}


ALLOWED_BATCH_TRANSITIONS = {
    ProcessingBatch.Status.DRAFT: {
        ProcessingBatch.Status.ASSIGNED,
        ProcessingBatch.Status.PRINTED,
        ProcessingBatch.Status.CANCELLED,
    },
    ProcessingBatch.Status.ASSIGNED: {
        ProcessingBatch.Status.PRINTED,
        ProcessingBatch.Status.COMPLETED,
        ProcessingBatch.Status.CANCELLED,
    },
    ProcessingBatch.Status.PRINTED: {
        ProcessingBatch.Status.COMPLETED,
        ProcessingBatch.Status.CANCELLED,
    },
    ProcessingBatch.Status.COMPLETED: set(),
    ProcessingBatch.Status.CANCELLED: set(),
}


class BiospecimenTransitionError(ValueError):
    pass


class AccessioningError(ValueError):
    pass


class BatchPlateError(ValueError):
    pass


class StorageInventoryError(ValueError):
    pass


def _next_sequence_payload(sample_type_id: str) -> tuple[str, str, int]:
    locked = BiospecimenType.objects.select_for_update().get(id=sample_type_id)
    sequence_value = locked.next_sequence
    locked.next_sequence += 1
    locked.save(update_fields=["next_sequence", "updated_at"])
    padded = str(sequence_value).zfill(locked.sequence_padding)
    return locked.identifier_prefix.strip(), locked.barcode_prefix.strip(), padded


def allocate_biospecimen_identifiers(
    sample_type: BiospecimenType, *, pooled: bool = False
) -> tuple[str, str]:
    with transaction.atomic():
        identifier_prefix, barcode_prefix, padded = _next_sequence_payload(
            str(sample_type.id)
        )
    if pooled:
        return f"{identifier_prefix}-POOL-{padded}", f"{barcode_prefix}-POOL-{padded}"
    return f"{identifier_prefix}-{padded}", f"{barcode_prefix}-{padded}"


def transition_biospecimen(specimen: Biospecimen, next_status: str) -> Biospecimen:
    allowed = ALLOWED_BIOSPECIMEN_TRANSITIONS.get(specimen.status, set())
    if next_status not in allowed:
        raise BiospecimenTransitionError("invalid_transition")
    specimen.status = next_status
    if next_status == Biospecimen.Status.RECEIVED and specimen.received_at is None:
        specimen.received_at = timezone.now()
    specimen.full_clean()
    specimen.save(update_fields=["status", "received_at", "updated_at"])
    return specimen


def transition_pool(pool: BiospecimenPool, next_status: str) -> BiospecimenPool:
    allowed = ALLOWED_POOL_TRANSITIONS.get(pool.status, set())
    if next_status not in allowed:
        raise BiospecimenTransitionError("invalid_transition")
    pool.status = next_status
    pool.full_clean()
    pool.save(update_fields=["status", "updated_at"])
    return pool


def create_aliquots(
    specimen: Biospecimen,
    *,
    count: int,
    quantity: Decimal,
    quantity_unit: str,
) -> list[Biospecimen]:
    if specimen.status not in {
        Biospecimen.Status.RECEIVED,
        Biospecimen.Status.AVAILABLE,
        Biospecimen.Status.ALIQUOTED,
    }:
        raise BiospecimenTransitionError("specimen_not_aliquotable")
    if count < 1 or count > 24:
        raise BiospecimenTransitionError("invalid_aliquot_count")
    lineage_root = specimen.lineage_root or specimen
    created: list[Biospecimen] = []
    for _ in range(count):
        sample_identifier, barcode = allocate_biospecimen_identifiers(
            specimen.sample_type
        )
        aliquot = Biospecimen(
            sample_type=specimen.sample_type,
            sample_identifier=sample_identifier,
            barcode=barcode,
            kind=Biospecimen.Kind.ALIQUOT,
            status=Biospecimen.Status.AVAILABLE,
            subject_identifier=specimen.subject_identifier,
            external_identifier=specimen.external_identifier,
            study=specimen.study,
            site=specimen.site,
            lab=specimen.lab,
            parent_specimen=specimen,
            lineage_root=lineage_root,
            quantity=quantity,
            quantity_unit=quantity_unit,
            metadata=dict(specimen.metadata or {}),
            collected_at=specimen.collected_at,
            received_at=specimen.received_at,
        )
        aliquot.full_clean()
        aliquot.save()
        created.append(aliquot)
    if specimen.status != Biospecimen.Status.ALIQUOTED:
        specimen.status = Biospecimen.Status.ALIQUOTED
        specimen.full_clean()
        specimen.save(update_fields=["status", "updated_at"])
    return created


def create_pool(
    *,
    sample_type: BiospecimenType,
    specimens: list[Biospecimen],
    quantity: Decimal,
    quantity_unit: str,
    study=None,
    site=None,
    lab=None,
    metadata: dict[str, object] | None = None,
) -> BiospecimenPool:
    if not specimens:
        raise BiospecimenTransitionError("specimens_required")
    specimen_ids = [str(specimen.id) for specimen in specimens]
    if len(specimen_ids) != len(set(specimen_ids)):
        raise BiospecimenTransitionError("duplicate_specimens")
    for specimen in specimens:
        if specimen.sample_type_id != sample_type.id:
            raise BiospecimenTransitionError("sample_type_mismatch")
        if specimen.status not in {
            Biospecimen.Status.RECEIVED,
            Biospecimen.Status.AVAILABLE,
            Biospecimen.Status.ALIQUOTED,
        }:
            raise BiospecimenTransitionError("specimen_not_poolable")

    pool_identifier, barcode = allocate_biospecimen_identifiers(
        sample_type, pooled=True
    )
    with transaction.atomic():
        pool = BiospecimenPool(
            sample_type=sample_type,
            pool_identifier=pool_identifier,
            barcode=barcode,
            status=BiospecimenPool.Status.ASSEMBLED,
            study=study,
            site=site,
            lab=lab,
            quantity=quantity,
            quantity_unit=quantity_unit,
            metadata=dict(metadata or {}),
        )
        pool.full_clean()
        pool.save()
        for specimen in specimens:
            member = BiospecimenPoolMember(
                pool=pool,
                specimen=specimen,
                contributed_quantity=specimen.quantity,
                contributed_unit=specimen.quantity_unit,
            )
            member.full_clean()
            member.save()
            specimen.status = Biospecimen.Status.POOLED
            specimen.full_clean()
            specimen.save(update_fields=["status", "updated_at"])
    return pool


def _latest_storage_record_for_biospecimen(
    specimen: Biospecimen,
) -> BiospecimenStorageRecord | None:
    return (
        specimen.storage_records.select_related("location")
        .order_by("-created_at")
        .first()
    )


def _latest_storage_record_for_pool(
    pool: BiospecimenPool,
) -> BiospecimenStorageRecord | None:
    return (
        pool.storage_records.select_related("location").order_by("-created_at").first()
    )


@transaction.atomic
def place_artifact_in_storage(
    *,
    location: StorageLocation,
    placed_by: str,
    reason: str,
    biospecimen: Biospecimen | None = None,
    biospecimen_pool: BiospecimenPool | None = None,
    notes: str = "",
    operation_run: OperationRun | None = None,
    task_run: TaskRun | None = None,
    submission_record: SubmissionRecord | None = None,
) -> BiospecimenStorageRecord:
    if (biospecimen is None) == (biospecimen_pool is None):
        raise StorageInventoryError("artifact_required")
    if submission_record and task_run is None:
        task_run = submission_record.task_run
    if task_run and operation_run is None:
        operation_run = task_run.operation_run
    artifact_lab_id = (
        biospecimen.lab_id if biospecimen is not None else biospecimen_pool.lab_id
    )
    if artifact_lab_id != location.lab_id:
        raise StorageInventoryError("location_lab_mismatch")
    latest_record = (
        _latest_storage_record_for_biospecimen(biospecimen)
        if biospecimen is not None
        else _latest_storage_record_for_pool(biospecimen_pool)
    )
    record = BiospecimenStorageRecord(
        biospecimen=biospecimen,
        biospecimen_pool=biospecimen_pool,
        location=location,
        previous_location=latest_record.location if latest_record else None,
        reason=reason,
        quantity_snapshot=(
            biospecimen.quantity
            if biospecimen is not None
            else biospecimen_pool.quantity
        ),
        quantity_unit=(
            biospecimen.quantity_unit
            if biospecimen is not None
            else biospecimen_pool.quantity_unit
        ),
        notes=notes.strip(),
        placed_by=placed_by.strip(),
        operation_run=operation_run,
        task_run=task_run,
        submission_record=submission_record,
    )
    record.full_clean()
    record.save()
    return record


@transaction.atomic
def create_inventory_lot(
    *,
    material: InventoryMaterial,
    lab,
    lot_number: str,
    received_quantity: Decimal,
    unit_of_measure: str,
    recorded_by: str,
    storage_location: StorageLocation | None = None,
    vendor: str = "",
    received_on: date | None = None,
    expires_on: date | None = None,
    notes: str = "",
    metadata: dict[str, object] | None = None,
) -> tuple[InventoryLot, InventoryTransaction]:
    if received_quantity < 0:
        raise StorageInventoryError("received_quantity_invalid")
    lot = InventoryLot(
        material=material,
        lab=lab,
        storage_location=storage_location,
        lot_number=lot_number.strip(),
        vendor=vendor.strip(),
        received_on=received_on or timezone.localdate(),
        expires_on=expires_on,
        notes=notes.strip(),
        initial_quantity=received_quantity,
        on_hand_quantity=received_quantity,
        unit_of_measure=unit_of_measure.strip() or material.default_unit,
        metadata=dict(metadata or {}),
    )
    lot.full_clean()
    lot.save()
    transaction_record = InventoryTransaction(
        lot=lot,
        transaction_type=InventoryTransaction.TransactionType.RECEIPT,
        quantity_delta=received_quantity,
        resulting_quantity=received_quantity,
        location=storage_location,
        notes=notes.strip(),
        recorded_by=recorded_by.strip(),
    )
    transaction_record.full_clean()
    transaction_record.save()
    return lot, transaction_record


@transaction.atomic
def record_inventory_transaction(
    *,
    lot: InventoryLot,
    transaction_type: str,
    quantity_delta: Decimal,
    recorded_by: str,
    location: StorageLocation | None = None,
    notes: str = "",
    biospecimen: Biospecimen | None = None,
    biospecimen_pool: BiospecimenPool | None = None,
    operation_run: OperationRun | None = None,
    task_run: TaskRun | None = None,
    submission_record: SubmissionRecord | None = None,
    material_usage_record: MaterialUsageRecord | None = None,
) -> InventoryTransaction:
    if submission_record and task_run is None:
        task_run = submission_record.task_run
    if task_run and operation_run is None:
        operation_run = task_run.operation_run
    if material_usage_record and operation_run is None:
        operation_run = material_usage_record.operation_run
    if material_usage_record and task_run is None:
        task_run = material_usage_record.task_run
    if transaction_type not in InventoryTransaction.TransactionType.values:
        raise StorageInventoryError("invalid_transaction_type")
    if (
        transaction_type == InventoryTransaction.TransactionType.TRANSFER
        and location is None
    ):
        raise StorageInventoryError("transfer_location_required")
    if (
        transaction_type
        in {
            InventoryTransaction.TransactionType.RECEIPT,
            InventoryTransaction.TransactionType.RELEASE,
        }
        and quantity_delta <= 0
    ):
        raise StorageInventoryError("quantity_delta_must_be_positive")
    if (
        transaction_type
        in {
            InventoryTransaction.TransactionType.RESERVATION,
            InventoryTransaction.TransactionType.CONSUMPTION,
            InventoryTransaction.TransactionType.DISPOSAL,
            InventoryTransaction.TransactionType.EXPIRY,
        }
        and quantity_delta >= 0
    ):
        raise StorageInventoryError("quantity_delta_must_be_negative")
    if (
        transaction_type == InventoryTransaction.TransactionType.ADJUSTMENT
        and quantity_delta == 0
    ):
        raise StorageInventoryError("quantity_delta_required")

    locked_lot = InventoryLot.objects.select_for_update().get(id=lot.id)
    resulting_quantity = locked_lot.on_hand_quantity + quantity_delta
    if resulting_quantity < 0:
        raise StorageInventoryError("insufficient_inventory")
    locked_lot.on_hand_quantity = resulting_quantity
    if location is not None:
        locked_lot.storage_location = location
    locked_lot.full_clean()
    locked_lot.save(
        update_fields=["on_hand_quantity", "storage_location", "updated_at"]
    )
    transaction_record = InventoryTransaction(
        lot=locked_lot,
        transaction_type=transaction_type,
        quantity_delta=quantity_delta,
        resulting_quantity=resulting_quantity,
        location=locked_lot.storage_location,
        biospecimen=biospecimen,
        biospecimen_pool=biospecimen_pool,
        operation_run=operation_run,
        task_run=task_run,
        submission_record=submission_record,
        material_usage_record=material_usage_record,
        notes=notes.strip(),
        recorded_by=recorded_by.strip(),
    )
    transaction_record.full_clean()
    transaction_record.save()
    return transaction_record


def generate_manifest_identifier() -> str:
    return f"ACC-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def _validate_sample_type_metadata(
    sample_type: BiospecimenType, metadata: dict[str, object]
) -> dict[str, object]:
    schema_version = resolve_schema_version_for_binding(
        target_type="sample_type", target_key=sample_type.key
    )
    if schema_version is None:
        return metadata
    result = validate_metadata_payload(schema_version, metadata)
    if not result.valid:
        raise AccessioningError(
            f"metadata_invalid:{json.dumps(result.errors, sort_keys=True)}"
        )
    return result.normalized_data


def submit_manifest(manifest: AccessioningManifest) -> AccessioningManifest:
    if manifest.status != AccessioningManifest.Status.DRAFT:
        raise AccessioningError("manifest_not_draft")
    if not manifest.items.exists():
        raise AccessioningError("manifest_items_required")
    manifest.status = AccessioningManifest.Status.SUBMITTED
    manifest.full_clean()
    manifest.save(update_fields=["status", "updated_at"])
    return manifest


def _manifest_status_from_items(manifest: AccessioningManifest) -> str:
    item_statuses = set(manifest.items.values_list("status", flat=True))
    if not item_statuses or item_statuses == {AccessioningManifestItem.Status.PENDING}:
        return AccessioningManifest.Status.SUBMITTED
    if item_statuses.issubset({AccessioningManifestItem.Status.RECEIVED}):
        return AccessioningManifest.Status.RECEIVED
    return AccessioningManifest.Status.RECEIVING


def _build_manifest_biospecimen(
    manifest: AccessioningManifest,
    item: AccessioningManifestItem,
    *,
    metadata: dict[str, object],
) -> Biospecimen:
    sample_identifier = item.expected_sample_identifier.strip()
    barcode = item.expected_barcode.strip()
    if not sample_identifier and not barcode:
        sample_identifier, barcode = allocate_biospecimen_identifiers(
            manifest.sample_type
        )
    elif not sample_identifier:
        sample_identifier, generated_barcode = allocate_biospecimen_identifiers(
            manifest.sample_type
        )
        barcode = barcode or generated_barcode
    elif not barcode:
        _, barcode = allocate_biospecimen_identifiers(manifest.sample_type)
    specimen = Biospecimen(
        sample_type=manifest.sample_type,
        sample_identifier=sample_identifier,
        barcode=barcode,
        kind=Biospecimen.Kind.PRIMARY,
        status=Biospecimen.Status.REGISTERED,
        subject_identifier=item.expected_subject_identifier,
        study=manifest.study,
        site=manifest.site,
        lab=manifest.lab,
        quantity=item.quantity,
        quantity_unit=item.quantity_unit,
        metadata=metadata,
    )
    specimen.full_clean()
    specimen.save()
    return specimen


def receive_manifest_item(
    item: AccessioningManifestItem,
    *,
    received_by: str,
    scan_value: str = "",
    notes: str = "",
    metadata: dict[str, object] | None = None,
    receipt_context: dict[str, object] | None = None,
    received_at=None,
) -> tuple[AccessioningManifestItem, ReceivingEvent]:
    if item.status == AccessioningManifestItem.Status.RECEIVED:
        raise AccessioningError("item_already_received")
    manifest = item.manifest
    if manifest.status == AccessioningManifest.Status.DRAFT:
        raise AccessioningError("manifest_not_submitted")
    candidate_values = {
        value.strip()
        for value in [item.expected_sample_identifier, item.expected_barcode]
        if isinstance(value, str) and value.strip()
    }
    if scan_value and candidate_values and scan_value.strip() not in candidate_values:
        raise AccessioningError("scan_mismatch")

    payload_metadata = dict(item.metadata or {})
    payload_metadata.update(metadata or {})
    normalized_metadata = _validate_sample_type_metadata(
        manifest.sample_type, payload_metadata
    )
    with transaction.atomic():
        specimen = item.biospecimen
        if specimen is None:
            specimen = _build_manifest_biospecimen(
                manifest, item, metadata=normalized_metadata
            )
        else:
            specimen.metadata = normalized_metadata
            specimen.quantity = item.quantity
            specimen.quantity_unit = item.quantity_unit
            specimen.full_clean()
            specimen.save(
                update_fields=["metadata", "quantity", "quantity_unit", "updated_at"]
            )
        if specimen.status == Biospecimen.Status.REGISTERED:
            transition_biospecimen(specimen, Biospecimen.Status.RECEIVED)
        elif specimen.status != Biospecimen.Status.RECEIVED:
            raise AccessioningError("specimen_not_receivable")

        now = received_at or timezone.now()
        if received_at and specimen.received_at != now:
            specimen.received_at = now
            specimen.full_clean()
            specimen.save(update_fields=["received_at", "updated_at"])
        item.biospecimen = specimen
        item.status = AccessioningManifestItem.Status.RECEIVED
        item.received_at = now
        item.notes = notes or item.notes
        item.metadata = normalized_metadata
        item.full_clean()
        item.save(
            update_fields=[
                "biospecimen",
                "status",
                "received_at",
                "notes",
                "metadata",
                "updated_at",
            ]
        )

        manifest.status = _manifest_status_from_items(manifest)
        if manifest.status == AccessioningManifest.Status.RECEIVED:
            manifest.received_at = now
        manifest.full_clean()
        update_fields = ["status", "updated_at"]
        if manifest.received_at:
            update_fields.append("received_at")
        manifest.save(update_fields=update_fields)

        event = ReceivingEvent(
            manifest=manifest,
            manifest_item=item,
            biospecimen=specimen,
            kind=ReceivingEvent.Kind.MANIFEST_ITEM,
            received_by=received_by,
            scan_value=scan_value.strip(),
            notes=notes,
            metadata=(
                {
                    "sample_metadata": normalized_metadata,
                    "receipt_context": dict(receipt_context or {}),
                }
                if receipt_context
                else normalized_metadata
            ),
            received_at=now,
        )
        event.full_clean()
        event.save()
    return item, event


def receive_single_biospecimen(
    *,
    sample_type: BiospecimenType,
    study,
    site,
    lab,
    subject_identifier: str,
    external_identifier: str,
    quantity: Decimal,
    quantity_unit: str,
    metadata: dict[str, object],
    received_by: str,
    sample_identifier: str = "",
    barcode: str = "",
    scan_value: str = "",
    notes: str = "",
    receipt_context: dict[str, object] | None = None,
    received_at=None,
) -> tuple[Biospecimen, ReceivingEvent]:
    normalized_metadata = _validate_sample_type_metadata(sample_type, metadata)
    if scan_value and barcode and scan_value.strip() != barcode.strip():
        raise AccessioningError("scan_mismatch")
    if not sample_identifier and not barcode:
        sample_identifier, barcode = allocate_biospecimen_identifiers(sample_type)
    elif not sample_identifier:
        sample_identifier, _ = allocate_biospecimen_identifiers(sample_type)
    elif not barcode:
        _, barcode = allocate_biospecimen_identifiers(sample_type)

    with transaction.atomic():
        specimen = Biospecimen(
            sample_type=sample_type,
            sample_identifier=sample_identifier.strip(),
            barcode=barcode.strip(),
            kind=Biospecimen.Kind.PRIMARY,
            status=Biospecimen.Status.REGISTERED,
            subject_identifier=subject_identifier.strip(),
            external_identifier=external_identifier.strip(),
            study=study,
            site=site,
            lab=lab,
            quantity=quantity,
            quantity_unit=quantity_unit.strip(),
            metadata=normalized_metadata,
            received_at=received_at,
        )
        specimen.full_clean()
        specimen.save()
        transition_biospecimen(specimen, Biospecimen.Status.RECEIVED)
        event = ReceivingEvent(
            biospecimen=specimen,
            kind=ReceivingEvent.Kind.SINGLE,
            received_by=received_by,
            scan_value=scan_value.strip(),
            notes=notes,
            metadata=(
                {
                    "sample_metadata": normalized_metadata,
                    "receipt_context": dict(receipt_context or {}),
                }
                if receipt_context
                else normalized_metadata
            ),
            received_at=received_at or timezone.now(),
        )
        event.full_clean()
        event.save()
    return specimen, event


def create_receiving_discrepancy(
    *,
    code: str,
    recorded_by: str,
    manifest: AccessioningManifest | None = None,
    manifest_item: AccessioningManifestItem | None = None,
    biospecimen: Biospecimen | None = None,
    notes: str = "",
    expected_data: dict[str, object] | None = None,
    actual_data: dict[str, object] | None = None,
) -> ReceivingDiscrepancy:
    discrepancy = ReceivingDiscrepancy(
        manifest=manifest,
        manifest_item=manifest_item,
        biospecimen=biospecimen,
        code=code,
        status=ReceivingDiscrepancy.Status.OPEN,
        notes=notes,
        expected_data=dict(expected_data or {}),
        actual_data=dict(actual_data or {}),
        recorded_by=recorded_by,
    )
    discrepancy.full_clean()
    discrepancy.save()
    if (
        manifest_item
        and manifest_item.status == AccessioningManifestItem.Status.PENDING
    ):
        manifest_item.status = AccessioningManifestItem.Status.DISCREPANT
        manifest_item.full_clean()
        manifest_item.save(update_fields=["status", "updated_at"])
        manifest = manifest or manifest_item.manifest
    if manifest:
        manifest.status = _manifest_status_from_items(manifest)
        manifest.full_clean()
        manifest.save(update_fields=["status", "updated_at"])
    return discrepancy


def accessioning_report(manifest: AccessioningManifest) -> dict[str, object]:
    items = list(
        manifest.items.select_related("biospecimen").order_by("position", "created_at")
    )
    discrepancies = list(manifest.discrepancies.order_by("-created_at"))
    events = list(
        manifest.receiving_events.select_related(
            "biospecimen", "manifest_item"
        ).order_by("-received_at")
    )
    return {
        "manifest": {
            "id": str(manifest.id),
            "manifest_identifier": manifest.manifest_identifier,
            "status": manifest.status,
            "sample_type_id": str(manifest.sample_type_id),
            "study_id": str(manifest.study_id) if manifest.study_id else None,
            "site_id": str(manifest.site_id) if manifest.site_id else None,
            "lab_id": str(manifest.lab_id) if manifest.lab_id else None,
            "source_system": manifest.source_system,
            "source_reference": manifest.source_reference,
            "received_at": (
                manifest.received_at.isoformat() if manifest.received_at else None
            ),
        },
        "summary": {
            "total_items": len(items),
            "received_items": sum(
                1
                for item in items
                if item.status == AccessioningManifestItem.Status.RECEIVED
            ),
            "discrepant_items": sum(
                1
                for item in items
                if item.status == AccessioningManifestItem.Status.DISCREPANT
            ),
            "open_discrepancies": sum(
                1
                for item in discrepancies
                if item.status == ReceivingDiscrepancy.Status.OPEN
            ),
            "receiving_events": len(events),
        },
        "items": [
            {
                "id": str(item.id),
                "position": item.position,
                "status": item.status,
                "expected_subject_identifier": item.expected_subject_identifier,
                "expected_sample_identifier": item.expected_sample_identifier,
                "expected_barcode": item.expected_barcode,
                "biospecimen_id": (
                    str(item.biospecimen_id) if item.biospecimen_id else None
                ),
                "received_at": (
                    item.received_at.isoformat() if item.received_at else None
                ),
                "notes": item.notes,
            }
            for item in items
        ],
        "discrepancies": [
            {
                "id": str(item.id),
                "code": item.code,
                "status": item.status,
                "manifest_item_id": (
                    str(item.manifest_item_id) if item.manifest_item_id else None
                ),
                "biospecimen_id": (
                    str(item.biospecimen_id) if item.biospecimen_id else None
                ),
                "notes": item.notes,
                "expected_data": item.expected_data,
                "actual_data": item.actual_data,
            }
            for item in discrepancies
        ],
        "events": [
            {
                "id": str(item.id),
                "kind": item.kind,
                "biospecimen_id": str(item.biospecimen_id),
                "manifest_item_id": (
                    str(item.manifest_item_id) if item.manifest_item_id else None
                ),
                "received_by": item.received_by,
                "scan_value": item.scan_value,
                "received_at": item.received_at.isoformat(),
            }
            for item in events
        ],
    }


def _plate_capacity(layout_template: PlateLayoutTemplate) -> int:
    return layout_template.rows * layout_template.columns


def _well_label_from_position(
    layout_template: PlateLayoutTemplate, position_index: int
) -> str:
    capacity = _plate_capacity(layout_template)
    if position_index < 1 or position_index > capacity:
        raise BatchPlateError("invalid_position_index")
    row_index = (position_index - 1) // layout_template.columns
    column_index = ((position_index - 1) % layout_template.columns) + 1
    return f"{chr(ord('A') + row_index)}{column_index}"


def _position_from_well_label(
    layout_template: PlateLayoutTemplate, well_label: str
) -> int:
    normalized = str(well_label or "").strip().upper()
    match = re.fullmatch(r"([A-Z])(\d{1,2})", normalized)
    if not match:
        raise BatchPlateError("invalid_well_label")
    row_label, column_raw = match.groups()
    row_index = ord(row_label) - ord("A")
    column_index = int(column_raw)
    if row_index < 0 or row_index >= layout_template.rows:
        raise BatchPlateError("invalid_well_label")
    if column_index < 1 or column_index > layout_template.columns:
        raise BatchPlateError("invalid_well_label")
    return (row_index * layout_template.columns) + column_index


def normalize_plate_position(
    layout_template: PlateLayoutTemplate,
    *,
    position_index: int | None = None,
    well_label: str = "",
) -> tuple[int, str]:
    if position_index is None and not str(well_label or "").strip():
        raise BatchPlateError("position_or_well_label_required")
    if position_index is None:
        resolved_position = _position_from_well_label(layout_template, well_label)
    else:
        resolved_position = int(position_index)
    resolved_label = _well_label_from_position(layout_template, resolved_position)
    return resolved_position, resolved_label


def generate_processing_batch_identifier(sample_type: BiospecimenType) -> str:
    prefix = sample_type.identifier_prefix.strip() or sample_type.key.upper()
    return f"{prefix}-BATCH-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"


def generate_batch_plate_identifier(batch_identifier: str, sequence_number: int) -> str:
    return f"{batch_identifier}-P{sequence_number:02d}"


def transition_processing_batch(
    batch: ProcessingBatch, next_status: str
) -> ProcessingBatch:
    allowed = ALLOWED_BATCH_TRANSITIONS.get(batch.status, set())
    if next_status not in allowed:
        raise BatchPlateError("invalid_transition")
    batch.status = next_status
    batch.full_clean()
    batch.save(update_fields=["status", "updated_at"])
    return batch


def _validate_assignable_specimen(
    specimen: Biospecimen, sample_type: BiospecimenType
) -> None:
    if specimen.sample_type_id != sample_type.id:
        raise BatchPlateError("sample_type_mismatch")
    if specimen.status not in {
        Biospecimen.Status.RECEIVED,
        Biospecimen.Status.AVAILABLE,
        Biospecimen.Status.ALIQUOTED,
    }:
        raise BatchPlateError("specimen_not_assignable")


def create_processing_batch(
    *,
    sample_type: BiospecimenType,
    plates: list[dict[str, object]],
    study=None,
    site=None,
    lab=None,
    notes: str = "",
    metadata: dict[str, object] | None = None,
    created_by: str = "",
) -> ProcessingBatch:
    if not plates:
        raise BatchPlateError("plates_required")

    with transaction.atomic():
        batch = ProcessingBatch(
            batch_identifier=generate_processing_batch_identifier(sample_type),
            sample_type=sample_type,
            study=study,
            site=site,
            lab=lab,
            status=ProcessingBatch.Status.DRAFT,
            notes=notes.strip(),
            metadata=dict(metadata or {}),
            created_by=created_by.strip(),
        )
        batch.full_clean()
        batch.save()

        assigned_specimen_ids: set[str] = set()
        for sequence_number, plate_spec in enumerate(plates, start=1):
            layout_template = plate_spec["layout_template"]
            if not isinstance(layout_template, PlateLayoutTemplate):
                raise BatchPlateError("layout_template_required")
            plate = BatchPlate(
                batch=batch,
                layout_template=layout_template,
                plate_identifier=generate_batch_plate_identifier(
                    batch.batch_identifier, sequence_number
                ),
                sequence_number=sequence_number,
                label=str(
                    plate_spec.get("label") or f"Plate {sequence_number}"
                ).strip(),
                metadata=dict(plate_spec.get("metadata") or {}),
            )
            plate.full_clean()
            plate.save()

            seen_positions: set[int] = set()
            assignments = plate_spec.get("assignments") or []
            if not isinstance(assignments, list):
                raise BatchPlateError("assignments_must_be_list")
            for assignment_spec in assignments:
                specimen = assignment_spec["biospecimen"]
                if not isinstance(specimen, Biospecimen):
                    raise BatchPlateError("biospecimen_required")
                _validate_assignable_specimen(specimen, sample_type)
                specimen_key = str(specimen.id)
                if specimen_key in assigned_specimen_ids:
                    raise BatchPlateError("duplicate_specimen_assignment")
                position_index, well_label = normalize_plate_position(
                    layout_template,
                    position_index=assignment_spec.get("position_index"),
                    well_label=str(assignment_spec.get("well_label") or ""),
                )
                if position_index in seen_positions:
                    raise BatchPlateError("duplicate_plate_position")
                assignment = BatchPlateAssignment(
                    plate=plate,
                    biospecimen=specimen,
                    position_index=position_index,
                    well_label=well_label,
                    metadata=dict(assignment_spec.get("metadata") or {}),
                )
                assignment.full_clean()
                assignment.save()
                seen_positions.add(position_index)
                assigned_specimen_ids.add(specimen_key)

    return batch


def processing_batch_worksheet(batch: ProcessingBatch) -> dict[str, object]:
    plates = list(
        batch.plates.select_related("layout_template")
        .prefetch_related("assignments__biospecimen")
        .order_by("sequence_number")
    )
    assignment_count = sum(plate.assignments.count() for plate in plates)
    plate_payloads: list[dict[str, object]] = []
    for plate in plates:
        assignments = list(
            plate.assignments.select_related("biospecimen").order_by("position_index")
        )
        plate_payloads.append(
            {
                "id": str(plate.id),
                "plate_identifier": plate.plate_identifier,
                "label": plate.label,
                "sequence_number": plate.sequence_number,
                "layout_template": {
                    "id": str(plate.layout_template_id),
                    "name": plate.layout_template.name,
                    "key": plate.layout_template.key,
                    "rows": plate.layout_template.rows,
                    "columns": plate.layout_template.columns,
                    "capacity": _plate_capacity(plate.layout_template),
                },
                "assignments": [
                    {
                        "id": str(item.id),
                        "biospecimen_id": str(item.biospecimen_id),
                        "sample_identifier": item.biospecimen.sample_identifier,
                        "barcode": item.biospecimen.barcode,
                        "subject_identifier": item.biospecimen.subject_identifier,
                        "position_index": item.position_index,
                        "well_label": item.well_label,
                        "metadata": item.metadata,
                    }
                    for item in assignments
                ],
            }
        )
    return {
        "batch": {
            "id": str(batch.id),
            "batch_identifier": batch.batch_identifier,
            "status": batch.status,
            "sample_type_id": str(batch.sample_type_id),
            "study_id": str(batch.study_id) if batch.study_id else None,
            "site_id": str(batch.site_id) if batch.site_id else None,
            "lab_id": str(batch.lab_id) if batch.lab_id else None,
            "notes": batch.notes,
            "metadata": batch.metadata,
            "created_by": batch.created_by,
        },
        "summary": {
            "plate_count": len(plates),
            "assigned_specimen_count": assignment_count,
        },
        "plates": plate_payloads,
    }


def create_processing_batch_worksheet_job(
    batch: ProcessingBatch,
    *,
    destination: str,
    template_ref: str = "a4/batch-rows",
    output_format: str = PrintJob.Format.PDF,
    pdf_sheet_preset: str = "a4-38x21.2",
) -> PrintJob:
    if output_format not in {PrintJob.Format.ZPL, PrintJob.Format.PDF}:
        raise BatchPlateError("invalid_output_format")
    worksheet = processing_batch_worksheet(batch)
    labels: list[dict[str, str]] = []
    for plate in worksheet["plates"]:
        for assignment in plate["assignments"]:
            labels.append(
                {
                    "content": assignment["barcode"] or assignment["sample_identifier"],
                    "title": f'{plate["plate_identifier"]} {assignment["well_label"]}',
                    "text": assignment["sample_identifier"],
                }
            )
    if not labels:
        raise BatchPlateError("batch_has_no_assignments")
    template = PrintTemplate.objects.filter(template_ref=template_ref).first()
    if template and template.output_format != output_format:
        raise BatchPlateError("template_output_format_mismatch")
    payload = {
        "batch_identifier": batch.batch_identifier,
        "labels": labels,
        "pdf_sheet_preset": pdf_sheet_preset,
        "plates": worksheet["plates"],
    }
    template_content = template.content if template else ""
    print_job = PrintJob.objects.create(
        template_ref=template_ref,
        payload=payload,
        output_format=output_format,
        destination=destination.strip() or "worksheet-preview",
        status=PrintJob.Status.PENDING,
        gateway_metadata={
            "render_preview": render_label_preview(
                output_format=output_format,
                template_content=template_content,
                payload=payload,
            )
        },
    )
    if batch.status != ProcessingBatch.Status.PRINTED:
        batch.status = ProcessingBatch.Status.PRINTED
        batch.full_clean()
        batch.save(update_fields=["status", "updated_at"])
    return print_job

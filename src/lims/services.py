from __future__ import annotations

import json
import re
from datetime import timedelta
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Callable
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urljoin, urlsplit

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from .models import (
    TanzaniaAddressSyncRun,
    TanzaniaDistrict,
    TanzaniaRegion,
    TanzaniaStreet,
    TanzaniaWard,
)

TANZANIA_POSTCODE_ROOT_URL = "https://www.tanzaniapostcode.com/"
POSTCODE_RE = re.compile(r"\b\d{5}\b")


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
        "regions_created": 0,
        "regions_updated": 0,
        "districts_created": 0,
        "districts_updated": 0,
        "wards_created": 0,
        "wards_updated": 0,
        "streets_created": 0,
        "streets_updated": 0,
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


def _upsert_region(link: ParsedLink):
    defaults = {
        "name": link.label,
        "slug": slugify(link.label),
        "source_url": link.url,
        "is_active": True,
        "last_synced_at": timezone.now(),
    }
    region, created = TanzaniaRegion.objects.update_or_create(
        source_path=link.path,
        defaults=defaults,
    )
    return region, created


def _upsert_district(region: TanzaniaRegion, link: ParsedLink):
    defaults = {
        "region": region,
        "name": link.label,
        "slug": slugify(link.label),
        "source_url": link.url,
        "is_active": True,
        "last_synced_at": timezone.now(),
    }
    district, created = TanzaniaDistrict.objects.update_or_create(
        source_path=link.path,
        defaults=defaults,
    )
    return district, created


def _upsert_ward(district: TanzaniaDistrict, link: ParsedLink):
    defaults = {
        "district": district,
        "name": link.label,
        "slug": slugify(link.label),
        "source_url": link.url,
        "is_active": True,
        "last_synced_at": timezone.now(),
    }
    ward, created = TanzaniaWard.objects.update_or_create(
        source_path=link.path,
        defaults=defaults,
    )
    return ward, created


def _upsert_street(ward: TanzaniaWard, link: ParsedLink, postcode: str):
    defaults = {
        "ward": ward,
        "name": link.label,
        "slug": slugify(link.label),
        "source_url": link.url,
        "postcode": postcode,
        "is_active": True,
        "last_synced_at": timezone.now(),
    }
    street, created = TanzaniaStreet.objects.update_or_create(
        source_path=link.path,
        defaults=defaults,
    )
    return street, created


def _process_item(
    run: TanzaniaAddressSyncRun,
    item: dict[str, str],
    html: str,
) -> None:
    level = item["level"]
    if level == "root":
        region_items: list[dict[str, str]] = []
        for link in parse_directory_links(html, item["url"]):
            region, created = _upsert_region(link)
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
        region = TanzaniaRegion.objects.get(id=item["region_id"])
        district_items: list[dict[str, str]] = []
        for link in parse_directory_links(html, item["url"]):
            district, created = _upsert_district(region, link)
            _increment_stat(run, "districts_created" if created else "districts_updated")
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
        district = TanzaniaDistrict.objects.get(id=item["district_id"])
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
        ward = TanzaniaWard.objects.get(id=item["ward_id"])
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
        ward = TanzaniaWard.objects.get(id=item["ward_id"])
        link = ParsedLink(
            label=item["street_label"],
            url=item["url"],
            path=item["street_path"],
        )
        street, created = _upsert_street(ward, link, parse_postcode(html))
        _increment_stat(run, "streets_created" if created else "streets_updated")
        return

    raise ValueError(f"unsupported_sync_level:{level}")


def sync_run_to_dict(run: TanzaniaAddressSyncRun) -> dict[str, object]:
    checkpoint = dict(run.checkpoint or {})
    return {
        "id": str(run.id),
        "mode": run.mode,
        "status": run.status,
        "source_root": run.source_root,
        "pages_processed": run.pages_processed,
        "request_budget": run.request_budget,
        "throttle_seconds": run.throttle_seconds,
        "queue_size": len(checkpoint.get("queue") or []),
        "stats": dict(run.stats or {}),
        "last_error": run.last_error or None,
        "triggered_by": run.triggered_by or None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "next_not_before_at": run.next_not_before_at.isoformat() if run.next_not_before_at else None,
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
    run.save(update_fields=["checkpoint", "stats", "started_at", "status", "last_error", "updated_at"])

    remaining_budget = max(1, run.request_budget)
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
            run.status = TanzaniaAddressSyncRun.Status.PAUSED
            run.last_error = str(exc)
            run.next_not_before_at = timezone.now() + timedelta(seconds=max(run.throttle_seconds, 5))
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
            run.next_not_before_at = timezone.now() + timedelta(seconds=run.throttle_seconds)
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

    run.status = TanzaniaAddressSyncRun.Status.PAUSED
    run.save(update_fields=["status", "updated_at"])
    return sync_run_to_dict(run)

from __future__ import annotations

import uuid

from django.db import models


class TimestampedUUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TanzaniaRegion(TimestampedUUIDModel):
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=220, blank=True, default="")
    source_path = models.CharField(max_length=500, unique=True)
    source_url = models.URLField(max_length=800)
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class TanzaniaDistrict(TimestampedUUIDModel):
    region = models.ForeignKey(
        TanzaniaRegion,
        on_delete=models.CASCADE,
        related_name="districts",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, blank=True, default="")
    source_path = models.CharField(max_length=500, unique=True)
    source_url = models.URLField(max_length=800)
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["region__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["region", "name"],
                name="uniq_lims_tz_district_per_region",
            )
        ]

    def __str__(self) -> str:
        return f"{self.region.name} / {self.name}"


class TanzaniaWard(TimestampedUUIDModel):
    district = models.ForeignKey(
        TanzaniaDistrict,
        on_delete=models.CASCADE,
        related_name="wards",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, blank=True, default="")
    source_path = models.CharField(max_length=500, unique=True)
    source_url = models.URLField(max_length=800)
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["district__region__name", "district__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["district", "name"],
                name="uniq_lims_tz_ward_per_district",
            )
        ]

    def __str__(self) -> str:
        return f"{self.district.name} / {self.name}"


class TanzaniaStreet(TimestampedUUIDModel):
    ward = models.ForeignKey(
        TanzaniaWard,
        on_delete=models.CASCADE,
        related_name="streets",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, blank=True, default="")
    source_path = models.CharField(max_length=500, unique=True)
    source_url = models.URLField(max_length=800)
    postcode = models.CharField(max_length=16, blank=True, default="")
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["ward__district__region__name", "ward__district__name", "ward__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["ward", "name"],
                name="uniq_lims_tz_street_per_ward",
            )
        ]

    def __str__(self) -> str:
        return f"{self.ward.name} / {self.name}"


class Lab(TimestampedUUIDModel):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=64, blank=True, default="")
    description = models.TextField(blank=True, default="")
    address_line = models.CharField(max_length=255, blank=True, default="")
    region = models.ForeignKey(
        TanzaniaRegion,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="labs",
    )
    district = models.ForeignKey(
        TanzaniaDistrict,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="labs",
    )
    ward = models.ForeignKey(
        TanzaniaWard,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="labs",
    )
    street = models.ForeignKey(
        TanzaniaStreet,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="labs",
    )
    postcode = models.CharField(max_length=16, blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"], name="lims_lab_name_idx"),
            models.Index(fields=["code"], name="lims_lab_code_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class Study(TimestampedUUIDModel):
    class Status(models.TextChoices):
        ACTIVE = "active"
        PAUSED = "paused"
        COMPLETED = "completed"

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=64, blank=True, default="")
    description = models.TextField(blank=True, default="")
    sponsor = models.CharField(max_length=200, blank=True, default="")
    lead_lab = models.ForeignKey(
        Lab,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lead_studies",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"], name="lims_study_name_idx"),
            models.Index(fields=["code"], name="lims_study_code_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class Site(TimestampedUUIDModel):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=64, blank=True, default="")
    description = models.TextField(blank=True, default="")
    study = models.ForeignKey(
        Study,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sites",
    )
    lab = models.ForeignKey(
        Lab,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sites",
    )
    address_line = models.CharField(max_length=255, blank=True, default="")
    region = models.ForeignKey(
        TanzaniaRegion,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sites",
    )
    district = models.ForeignKey(
        TanzaniaDistrict,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sites",
    )
    ward = models.ForeignKey(
        TanzaniaWard,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sites",
    )
    street = models.ForeignKey(
        TanzaniaStreet,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sites",
    )
    postcode = models.CharField(max_length=16, blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"], name="lims_site_name_idx"),
            models.Index(fields=["code"], name="lims_site_code_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class TanzaniaAddressSyncRun(TimestampedUUIDModel):
    class Status(models.TextChoices):
        PENDING = "pending"
        RUNNING = "running"
        PAUSED = "paused"
        COMPLETED = "completed"
        FAILED = "failed"

    class Mode(models.TextChoices):
        FULL_REFRESH = "full_refresh"
        INCREMENTAL = "incremental"

    mode = models.CharField(max_length=24, choices=Mode.choices, default=Mode.INCREMENTAL)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    source_root = models.URLField(max_length=800, default="https://www.tanzaniapostcode.com/")
    checkpoint = models.JSONField(default=dict, blank=True)
    stats = models.JSONField(default=dict, blank=True)
    request_budget = models.PositiveIntegerField(default=10)
    throttle_seconds = models.PositiveIntegerField(default=2)
    pages_processed = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    next_not_before_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    triggered_by = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="lims_addr_sync_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.mode}:{self.status}:{self.created_at.isoformat()}"

from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


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


class MetadataVocabulary(TimestampedUUIDModel):
    name = models.CharField(max_length=200)
    code = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["code"], name="lims_meta_vocab_code_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class MetadataVocabularyItem(TimestampedUUIDModel):
    vocabulary = models.ForeignKey(
        MetadataVocabulary,
        on_delete=models.CASCADE,
        related_name="items",
    )
    value = models.CharField(max_length=100)
    label = models.CharField(max_length=200)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["vocabulary__name", "sort_order", "label"]
        constraints = [
            models.UniqueConstraint(
                fields=["vocabulary", "value"],
                name="uniq_lims_meta_vocab_item_value",
            )
        ]

    def __str__(self) -> str:
        return f"{self.vocabulary.name}: {self.label}"


class MetadataFieldDefinition(TimestampedUUIDModel):
    class FieldType(models.TextChoices):
        TEXT = "text"
        LONG_TEXT = "long_text"
        INTEGER = "integer"
        DECIMAL = "decimal"
        BOOLEAN = "boolean"
        DATE = "date"
        DATETIME = "datetime"
        CHOICE = "choice"
        MULTI_CHOICE = "multi_choice"

    name = models.CharField(max_length=200)
    code = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    field_type = models.CharField(max_length=32, choices=FieldType.choices)
    help_text = models.CharField(max_length=255, blank=True, default="")
    placeholder = models.CharField(max_length=255, blank=True, default="")
    vocabulary = models.ForeignKey(
        MetadataVocabulary,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="field_definitions",
    )
    default_value = models.JSONField(null=True, blank=True)
    config = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["code"], name="lims_meta_field_code_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        choice_types = {self.FieldType.CHOICE, self.FieldType.MULTI_CHOICE}
        if self.field_type in choice_types and not self.vocabulary_id:
            raise ValidationError({"vocabulary": "choice fields require a vocabulary"})
        if self.field_type not in choice_types and self.vocabulary_id:
            raise ValidationError({"vocabulary": "vocabulary is only valid for choice fields"})
        if not isinstance(self.config, dict):
            raise ValidationError({"config": "config must be an object"})

    def __str__(self) -> str:
        return self.name


class MetadataSchema(TimestampedUUIDModel):
    name = models.CharField(max_length=200)
    code = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["code"], name="lims_meta_schema_code_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class MetadataSchemaVersion(TimestampedUUIDModel):
    class Status(models.TextChoices):
        DRAFT = "draft"
        PUBLISHED = "published"
        DEPRECATED = "deprecated"

    schema = models.ForeignKey(
        MetadataSchema,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version_number = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    change_summary = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["schema__name", "-version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["schema", "version_number"],
                name="uniq_lims_meta_schema_version_number",
            )
        ]

    def __str__(self) -> str:
        return f"{self.schema.code}:v{self.version_number}"


class MetadataSchemaField(TimestampedUUIDModel):
    schema_version = models.ForeignKey(
        MetadataSchemaVersion,
        on_delete=models.CASCADE,
        related_name="fields",
    )
    field_definition = models.ForeignKey(
        MetadataFieldDefinition,
        on_delete=models.PROTECT,
        related_name="schema_fields",
    )
    field_key = models.SlugField(max_length=100)
    position = models.PositiveIntegerField(default=0)
    required = models.BooleanField(default=False)
    validation_rules = models.JSONField(default=dict, blank=True)
    condition = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["schema_version__schema__name", "schema_version__version_number", "position", "field_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["schema_version", "field_key"],
                name="uniq_lims_meta_schema_field_key",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if not self.field_key:
            raise ValidationError({"field_key": "field_key is required"})
        if not isinstance(self.validation_rules, dict):
            raise ValidationError({"validation_rules": "validation_rules must be an object"})
        if not isinstance(self.condition, dict):
            raise ValidationError({"condition": "condition must be an object"})

    def __str__(self) -> str:
        return f"{self.schema_version} / {self.field_key}"


class MetadataSchemaBinding(TimestampedUUIDModel):
    class TargetType(models.TextChoices):
        SAMPLE_TYPE = "sample_type"
        WORKFLOW_STEP = "workflow_step"

    schema_version = models.ForeignKey(
        MetadataSchemaVersion,
        on_delete=models.CASCADE,
        related_name="bindings",
    )
    target_type = models.CharField(max_length=32, choices=TargetType.choices)
    target_key = models.SlugField(max_length=100)
    target_label = models.CharField(max_length=200, blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["target_type", "target_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["target_type", "target_key"],
                name="uniq_lims_meta_schema_binding_target",
            )
        ]
        indexes = [
            models.Index(fields=["target_type", "target_key"], name="lims_meta_binding_target_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.target_type}:{self.target_key}"


class BiospecimenType(TimestampedUUIDModel):
    name = models.CharField(max_length=200)
    key = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    identifier_prefix = models.CharField(max_length=32, default="SPEC")
    barcode_prefix = models.CharField(max_length=32, default="BC")
    sequence_padding = models.PositiveIntegerField(default=6)
    next_sequence = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["key"], name="lims_bios_type_key_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.sequence_padding < 3 or self.sequence_padding > 12:
            raise ValidationError({"sequence_padding": "sequence_padding must be between 3 and 12"})
        if not self.identifier_prefix.strip():
            raise ValidationError({"identifier_prefix": "identifier_prefix is required"})
        if not self.barcode_prefix.strip():
            raise ValidationError({"barcode_prefix": "barcode_prefix is required"})

    def __str__(self) -> str:
        return self.name


class Biospecimen(TimestampedUUIDModel):
    class Kind(models.TextChoices):
        PRIMARY = "primary"
        ALIQUOT = "aliquot"

    class Status(models.TextChoices):
        REGISTERED = "registered"
        RECEIVED = "received"
        AVAILABLE = "available"
        ALIQUOTED = "aliquoted"
        POOLED = "pooled"
        CONSUMED = "consumed"
        ARCHIVED = "archived"
        DISPOSED = "disposed"

    sample_type = models.ForeignKey(
        BiospecimenType,
        on_delete=models.PROTECT,
        related_name="biospecimens",
    )
    sample_identifier = models.CharField(max_length=64, unique=True)
    barcode = models.CharField(max_length=64, unique=True)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.PRIMARY)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.REGISTERED)
    subject_identifier = models.CharField(max_length=100, blank=True, default="")
    external_identifier = models.CharField(max_length=100, blank=True, default="")
    study = models.ForeignKey(
        Study,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="biospecimens",
    )
    site = models.ForeignKey(
        Site,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="biospecimens",
    )
    lab = models.ForeignKey(
        Lab,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="biospecimens",
    )
    parent_specimen = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="aliquots",
    )
    lineage_root = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="lineage_descendants",
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_unit = models.CharField(max_length=32, blank=True, default="mL")
    metadata = models.JSONField(default=dict, blank=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["sample_identifier"], name="lims_bio_sample_id_idx"),
            models.Index(fields=["barcode"], name="lims_bio_barcode_idx"),
            models.Index(fields=["status", "-created_at"], name="lims_bio_status_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.parent_specimen_id and self.parent_specimen_id == self.id:
            raise ValidationError({"parent_specimen": "parent_specimen cannot reference itself"})
        if self.lineage_root_id and self.lineage_root_id == self.id:
            raise ValidationError({"lineage_root": "lineage_root cannot reference itself"})
        if self.kind == self.Kind.PRIMARY and self.parent_specimen_id:
            raise ValidationError({"parent_specimen": "primary specimens cannot define a parent"})
        if self.kind == self.Kind.ALIQUOT and not self.parent_specimen_id:
            raise ValidationError({"parent_specimen": "aliquots require a parent specimen"})
        if self.parent_specimen_id and self.sample_type_id and self.parent_specimen.sample_type_id != self.sample_type_id:
            raise ValidationError({"sample_type": "aliquots must use the same sample type as the parent"})
        if not isinstance(self.metadata, dict):
            raise ValidationError({"metadata": "metadata must be an object"})

    def __str__(self) -> str:
        return self.sample_identifier


class BiospecimenPool(TimestampedUUIDModel):
    class Status(models.TextChoices):
        ASSEMBLED = "assembled"
        CONSUMED = "consumed"
        ARCHIVED = "archived"

    sample_type = models.ForeignKey(
        BiospecimenType,
        on_delete=models.PROTECT,
        related_name="pools",
    )
    pool_identifier = models.CharField(max_length=64, unique=True)
    barcode = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ASSEMBLED)
    study = models.ForeignKey(
        Study,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="biospecimen_pools",
    )
    site = models.ForeignKey(
        Site,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="biospecimen_pools",
    )
    lab = models.ForeignKey(
        Lab,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="biospecimen_pools",
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_unit = models.CharField(max_length=32, blank=True, default="mL")
    metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["pool_identifier"], name="lims_bio_pool_id_idx"),
            models.Index(fields=["status", "-created_at"], name="lims_bio_pool_status_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if not isinstance(self.metadata, dict):
            raise ValidationError({"metadata": "metadata must be an object"})

    def __str__(self) -> str:
        return self.pool_identifier


class BiospecimenPoolMember(TimestampedUUIDModel):
    pool = models.ForeignKey(
        BiospecimenPool,
        on_delete=models.CASCADE,
        related_name="members",
    )
    specimen = models.ForeignKey(
        Biospecimen,
        on_delete=models.PROTECT,
        related_name="pool_memberships",
    )
    contributed_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    contributed_unit = models.CharField(max_length=32, blank=True, default="mL")

    class Meta:
        ordering = ["pool__pool_identifier", "specimen__sample_identifier"]
        constraints = [
            models.UniqueConstraint(
                fields=["pool", "specimen"],
                name="uniq_lims_bio_pool_member",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.pool_id and self.specimen_id and self.pool.sample_type_id != self.specimen.sample_type_id:
            raise ValidationError({"specimen": "pool members must share the same sample type as the pool"})

    def __str__(self) -> str:
        return f"{self.pool.pool_identifier}:{self.specimen.sample_identifier}"


class AccessioningManifest(TimestampedUUIDModel):
    class Status(models.TextChoices):
        DRAFT = "draft"
        SUBMITTED = "submitted"
        RECEIVING = "receiving"
        RECEIVED = "received"

    manifest_identifier = models.CharField(max_length=64, unique=True)
    sample_type = models.ForeignKey(
        BiospecimenType,
        on_delete=models.PROTECT,
        related_name="accessioning_manifests",
    )
    study = models.ForeignKey(
        Study,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="accessioning_manifests",
    )
    site = models.ForeignKey(
        Site,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="accessioning_manifests",
    )
    lab = models.ForeignKey(
        Lab,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="accessioning_manifests",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    source_system = models.CharField(max_length=100, blank=True, default="")
    source_reference = models.CharField(max_length=100, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.CharField(max_length=100, blank=True, default="")
    received_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["manifest_identifier"], name="lims_acc_manifest_id_idx"),
            models.Index(fields=["status", "-created_at"], name="lims_acc_manifest_status_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if not isinstance(self.metadata, dict):
            raise ValidationError({"metadata": "metadata must be an object"})

    def __str__(self) -> str:
        return self.manifest_identifier


class AccessioningManifestItem(TimestampedUUIDModel):
    class Status(models.TextChoices):
        PENDING = "pending"
        RECEIVED = "received"
        DISCREPANT = "discrepant"

    manifest = models.ForeignKey(
        AccessioningManifest,
        on_delete=models.CASCADE,
        related_name="items",
    )
    biospecimen = models.ForeignKey(
        Biospecimen,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="manifest_items",
    )
    position = models.PositiveIntegerField(default=1)
    expected_subject_identifier = models.CharField(max_length=100, blank=True, default="")
    expected_sample_identifier = models.CharField(max_length=64, blank=True, default="")
    expected_barcode = models.CharField(max_length=64, blank=True, default="")
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_unit = models.CharField(max_length=32, blank=True, default="mL")
    collection_status = models.CharField(max_length=32, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    received_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["manifest__manifest_identifier", "position", "created_at"]
        indexes = [
            models.Index(fields=["manifest", "status"], name="lims_acc_item_status_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["manifest", "position"], name="uniq_lims_acc_manifest_item_position"),
        ]

    def clean(self) -> None:
        super().clean()
        if not isinstance(self.metadata, dict):
            raise ValidationError({"metadata": "metadata must be an object"})

    def __str__(self) -> str:
        return f"{self.manifest.manifest_identifier}:{self.position}"


class ReceivingEvent(TimestampedUUIDModel):
    class Kind(models.TextChoices):
        SINGLE = "single"
        MANIFEST_ITEM = "manifest_item"

    manifest = models.ForeignKey(
        AccessioningManifest,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="receiving_events",
    )
    manifest_item = models.ForeignKey(
        AccessioningManifestItem,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="receiving_events",
    )
    biospecimen = models.ForeignKey(
        Biospecimen,
        on_delete=models.PROTECT,
        related_name="receiving_events",
    )
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.SINGLE)
    received_by = models.CharField(max_length=100, blank=True, default="")
    scan_value = models.CharField(max_length=100, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    received_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-received_at", "-created_at"]
        indexes = [
            models.Index(fields=["received_at"], name="lims_recv_evt_recv_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if not isinstance(self.metadata, dict):
            raise ValidationError({"metadata": "metadata must be an object"})
        if self.manifest_item_id and self.manifest_id and self.manifest_item.manifest_id != self.manifest_id:
            raise ValidationError({"manifest_item": "manifest_item must belong to the manifest"})

    def __str__(self) -> str:
        return f"{self.kind}:{self.biospecimen.sample_identifier}"


class ReceivingDiscrepancy(TimestampedUUIDModel):
    class Code(models.TextChoices):
        BARCODE_MISMATCH = "barcode_mismatch"
        IDENTIFIER_MISMATCH = "identifier_mismatch"
        MISSING_SAMPLE = "missing_sample"
        DAMAGED_SAMPLE = "damaged_sample"
        METADATA_MISMATCH = "metadata_mismatch"
        OTHER = "other"

    class Status(models.TextChoices):
        OPEN = "open"
        RESOLVED = "resolved"

    manifest = models.ForeignKey(
        AccessioningManifest,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="discrepancies",
    )
    manifest_item = models.ForeignKey(
        AccessioningManifestItem,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="discrepancies",
    )
    biospecimen = models.ForeignKey(
        Biospecimen,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="receiving_discrepancies",
    )
    code = models.CharField(max_length=32, choices=Code.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    notes = models.TextField(blank=True, default="")
    expected_data = models.JSONField(default=dict, blank=True)
    actual_data = models.JSONField(default=dict, blank=True)
    recorded_by = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="lims_receiving_disc_status_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if not isinstance(self.expected_data, dict):
            raise ValidationError({"expected_data": "expected_data must be an object"})
        if not isinstance(self.actual_data, dict):
            raise ValidationError({"actual_data": "actual_data must be an object"})
        if self.manifest_item_id and self.manifest_id and self.manifest_item.manifest_id != self.manifest_id:
            raise ValidationError({"manifest_item": "manifest_item must belong to the manifest"})

    def __str__(self) -> str:
        return f"{self.code}:{self.status}"

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


def _validate_address_hierarchy(*, country=None, region=None, district=None, ward=None, street=None) -> None:
    if street and ward and street.ward_id != ward.id:
        raise ValidationError({"street": "Selected street does not belong to the selected ward."})
    if ward and district and ward.district_id != district.id:
        raise ValidationError({"ward": "Selected ward does not belong to the selected district."})
    if district and region and district.region_id != region.id:
        raise ValidationError({"district": "Selected district does not belong to the selected region."})
    if region and country and region.country_id != country.id:
        raise ValidationError({"region": "Selected region does not belong to the selected country."})


class Country(TimestampedUUIDModel):
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=8, unique=True)
    slug = models.SlugField(max_length=220, blank=True, default="")
    source_url = models.URLField(max_length=800, blank=True, default="")
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Region(TimestampedUUIDModel):
    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="regions",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, blank=True, default="")
    source_path = models.CharField(max_length=500, unique=True)
    source_url = models.URLField(max_length=800)
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["country__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["country", "name"],
                name="uniq_lims_region_per_country",
            )
        ]

    def __str__(self) -> str:
        return f"{self.country.name} / {self.name}"


class District(TimestampedUUIDModel):
    region = models.ForeignKey(
        Region,
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
                name="uniq_lims_district_per_region",
            )
        ]

    def __str__(self) -> str:
        return f"{self.region.name} / {self.name}"


class Ward(TimestampedUUIDModel):
    district = models.ForeignKey(
        District,
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
                name="uniq_lims_ward_per_district",
            )
        ]

    def __str__(self) -> str:
        return f"{self.district.name} / {self.name}"


class Street(TimestampedUUIDModel):
    ward = models.ForeignKey(
        Ward,
        on_delete=models.CASCADE,
        related_name="streets",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, blank=True, default="")
    source_path = models.CharField(max_length=500, unique=True)
    source_url = models.URLField(max_length=800)
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["ward__district__region__name", "ward__district__name", "ward__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["ward", "name"],
                name="uniq_lims_street_per_ward",
            )
        ]

    def __str__(self) -> str:
        return f"{self.ward.name} / {self.name}"


class Postcode(TimestampedUUIDModel):
    street = models.ForeignKey(
        Street,
        on_delete=models.CASCADE,
        related_name="postcodes",
    )
    code = models.CharField(max_length=16)
    source_path = models.CharField(max_length=500, unique=True)
    source_url = models.URLField(max_length=800)
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["street__ward__district__region__country__name", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["street", "code"],
                name="uniq_lims_postcode_per_street",
            )
        ]

    def __str__(self) -> str:
        return self.code


class Lab(TimestampedUUIDModel):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=64, blank=True, default="")
    description = models.TextField(blank=True, default="")
    address_line = models.CharField(max_length=255, blank=True, default="")
    country = models.ForeignKey(
        Country,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="labs",
    )
    region = models.ForeignKey(
        Region,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="labs",
    )
    district = models.ForeignKey(
        District,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="labs",
    )
    ward = models.ForeignKey(
        Ward,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="labs",
    )
    street = models.ForeignKey(
        Street,
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

    def clean(self) -> None:
        super().clean()
        _validate_address_hierarchy(
            country=self.country,
            region=self.region,
            district=self.district,
            ward=self.ward,
            street=self.street,
        )


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
    studies = models.ManyToManyField(
        Study,
        blank=True,
        related_name="linked_sites",
    )
    lab = models.ForeignKey(
        Lab,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sites",
    )
    address_line = models.CharField(max_length=255, blank=True, default="")
    country = models.ForeignKey(
        Country,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sites",
    )
    region = models.ForeignKey(
        Region,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sites",
    )
    district = models.ForeignKey(
        District,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sites",
    )
    ward = models.ForeignKey(
        Ward,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sites",
    )
    street = models.ForeignKey(
        Street,
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

    def clean(self) -> None:
        super().clean()
        _validate_address_hierarchy(
            country=self.country,
            region=self.region,
            district=self.district,
            ward=self.ward,
            street=self.street,
        )


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


class MetadataVocabularyDomain(TimestampedUUIDModel):
    name = models.CharField(max_length=200)
    code = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["code"], name="lims_meta_vdom_code_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class MetadataVocabulary(TimestampedUUIDModel):
    name = models.CharField(max_length=200)
    code = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    domain = models.ForeignKey(
        MetadataVocabularyDomain,
        on_delete=models.PROTECT,
        related_name="vocabularies",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["code"], name="lims_meta_vocab_code_idx"),
            models.Index(fields=["domain", "name"], name="lims_meta_vocab_dname_idx"),
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
    purpose = models.CharField(max_length=200, blank=True, default="")
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
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="schema_fields",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    field_type = models.CharField(max_length=32, choices=MetadataFieldDefinition.FieldType.choices)
    field_key = models.SlugField(max_length=100)
    help_text = models.CharField(max_length=255, blank=True, default="")
    placeholder = models.CharField(max_length=255, blank=True, default="")
    vocabulary = models.ForeignKey(
        MetadataVocabulary,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="schema_fields",
    )
    default_value = models.JSONField(null=True, blank=True)
    config = models.JSONField(default=dict, blank=True)
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
        choice_types = {
            MetadataFieldDefinition.FieldType.CHOICE,
            MetadataFieldDefinition.FieldType.MULTI_CHOICE,
        }
        if self.field_type in choice_types and not self.vocabulary_id:
            raise ValidationError({"vocabulary": "choice fields require a vocabulary"})
        if self.field_type not in choice_types and self.vocabulary_id:
            raise ValidationError({"vocabulary": "vocabulary is only valid for choice fields"})
        if not isinstance(self.config, dict):
            raise ValidationError({"config": "config must be an object"})
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


class WorkflowTemplate(TimestampedUUIDModel):
    name = models.CharField(max_length=200)
    code = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    purpose = models.CharField(max_length=200, blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["code"], name="lims_wf_template_code_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class WorkflowTemplateVersion(TimestampedUUIDModel):
    class Status(models.TextChoices):
        DRAFT = "draft"
        PUBLISHED = "published"
        DEPRECATED = "deprecated"

    template = models.ForeignKey(
        WorkflowTemplate,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version_number = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    change_summary = models.CharField(max_length=255, blank=True, default="")
    compiled_definition = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["template__name", "-version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["template", "version_number"],
                name="uniq_lims_wf_template_version_number",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if not isinstance(self.compiled_definition, dict):
            raise ValidationError({"compiled_definition": "compiled_definition must be an object"})

    def __str__(self) -> str:
        return f"{self.template.code}:v{self.version_number}"


class WorkflowNodeTemplate(TimestampedUUIDModel):
    class NodeType(models.TextChoices):
        START = "start"
        START_HANDLE = "start_handle"
        VIEW = "view"
        FUNCTION = "function"
        HANDLE = "handle"
        IF = "if"
        SWITCH = "switch"
        SPLIT = "split"
        SPLIT_FIRST = "split_first"
        JOIN = "join"
        END = "end"

    workflow_version = models.ForeignKey(
        WorkflowTemplateVersion,
        on_delete=models.CASCADE,
        related_name="nodes",
    )
    node_key = models.SlugField(max_length=100)
    node_type = models.CharField(max_length=32, choices=NodeType.choices)
    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True, default="")
    position = models.PositiveIntegerField(default=0)
    assignment_role = models.CharField(max_length=100, blank=True, default="")
    permission_key = models.CharField(max_length=100, blank=True, default="")
    requires_approval = models.BooleanField(default=False)
    approval_role = models.CharField(max_length=100, blank=True, default="")
    config = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["workflow_version__template__name", "position", "node_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["workflow_version", "node_key"],
                name="uniq_lims_wf_node_per_version",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if not isinstance(self.config, dict):
            raise ValidationError({"config": "config must be an object"})
        if self.requires_approval and not self.approval_role.strip():
            raise ValidationError({"approval_role": "approval_role is required when requires_approval is true"})

    def __str__(self) -> str:
        return f"{self.workflow_version} / {self.node_key}"


class WorkflowEdgeTemplate(TimestampedUUIDModel):
    workflow_version = models.ForeignKey(
        WorkflowTemplateVersion,
        on_delete=models.CASCADE,
        related_name="edges",
    )
    source_node = models.ForeignKey(
        WorkflowNodeTemplate,
        on_delete=models.CASCADE,
        related_name="outgoing_edges",
    )
    target_node = models.ForeignKey(
        WorkflowNodeTemplate,
        on_delete=models.CASCADE,
        related_name="incoming_edges",
    )
    priority = models.PositiveIntegerField(default=0)
    condition = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["workflow_version__template__name", "priority", "source_node__node_key", "target_node__node_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["workflow_version", "source_node", "target_node", "priority"],
                name="uniq_lims_wf_edge_priority",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if not isinstance(self.condition, dict):
            raise ValidationError({"condition": "condition must be an object"})
        if self.source_node_id and self.source_node.workflow_version_id != self.workflow_version_id:
            raise ValidationError({"source_node": "source_node must belong to the same workflow version"})
        if self.target_node_id and self.target_node.workflow_version_id != self.workflow_version_id:
            raise ValidationError({"target_node": "target_node must belong to the same workflow version"})
        if self.source_node_id and self.target_node_id and self.source_node_id == self.target_node_id:
            raise ValidationError({"target_node": "source_node and target_node must differ"})

    def __str__(self) -> str:
        return f"{self.source_node.node_key} -> {self.target_node.node_key}"


class WorkflowStepBinding(TimestampedUUIDModel):
    class BindingType(models.TextChoices):
        FULL_SCHEMA = "full_schema"
        UI_STEP = "ui_step"
        FIELD_SET = "field_set"

    node = models.ForeignKey(
        WorkflowNodeTemplate,
        on_delete=models.CASCADE,
        related_name="step_bindings",
    )
    schema_version = models.ForeignKey(
        MetadataSchemaVersion,
        on_delete=models.CASCADE,
        related_name="workflow_step_bindings",
    )
    binding_type = models.CharField(max_length=32, choices=BindingType.choices, default=BindingType.FULL_SCHEMA)
    ui_step = models.SlugField(max_length=100, blank=True, default="")
    field_keys = models.JSONField(default=list, blank=True)
    is_required = models.BooleanField(default=True)

    class Meta:
        ordering = ["node__workflow_version__template__name", "node__position", "schema_version__schema__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["node", "schema_version", "binding_type", "ui_step"],
                name="uniq_lims_wf_step_binding_scope",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.schema_version_id and self.schema_version.status != MetadataSchemaVersion.Status.PUBLISHED:
            raise ValidationError({"schema_version": "schema_version must be published"})
        if not isinstance(self.field_keys, list) or not all(isinstance(item, str) for item in self.field_keys):
            raise ValidationError({"field_keys": "field_keys must be a list of strings"})
        if self.binding_type == self.BindingType.UI_STEP and not self.ui_step:
            raise ValidationError({"ui_step": "ui_step is required for ui_step bindings"})
        if self.binding_type == self.BindingType.FIELD_SET and not self.field_keys:
            raise ValidationError({"field_keys": "field_keys are required for field_set bindings"})
        if self.binding_type == self.BindingType.FULL_SCHEMA and (self.ui_step or self.field_keys):
            raise ValidationError({"binding_type": "full_schema bindings cannot set ui_step or field_keys"})
        if self.binding_type == self.BindingType.UI_STEP and self.field_keys:
            raise ValidationError({"field_keys": "ui_step bindings cannot set field_keys"})

    def __str__(self) -> str:
        return f"{self.node.node_key} -> {self.schema_version}"


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


class PlateLayoutTemplate(TimestampedUUIDModel):
    name = models.CharField(max_length=200)
    key = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    rows = models.PositiveIntegerField(default=8)
    columns = models.PositiveIntegerField(default=12)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["key"], name="lims_plate_layout_key_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["rows", "columns"], name="uniq_lims_plate_layout_dims"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.rows < 1 or self.rows > 26:
            raise ValidationError({"rows": "rows must be between 1 and 26"})
        if self.columns < 1 or self.columns > 48:
            raise ValidationError({"columns": "columns must be between 1 and 48"})

    def __str__(self) -> str:
        return self.name


class ProcessingBatch(TimestampedUUIDModel):
    class Status(models.TextChoices):
        DRAFT = "draft"
        ASSIGNED = "assigned"
        PRINTED = "printed"
        COMPLETED = "completed"
        CANCELLED = "cancelled"

    batch_identifier = models.CharField(max_length=80, unique=True)
    sample_type = models.ForeignKey(
        BiospecimenType,
        on_delete=models.PROTECT,
        related_name="processing_batches",
    )
    study = models.ForeignKey(
        Study,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="processing_batches",
    )
    site = models.ForeignKey(
        Site,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="processing_batches",
    )
    lab = models.ForeignKey(
        Lab,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="processing_batches",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    notes = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["batch_identifier"], name="lims_proc_batch_id_idx"),
            models.Index(fields=["status", "-created_at"], name="lims_proc_batch_status_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if not isinstance(self.metadata, dict):
            raise ValidationError({"metadata": "metadata must be an object"})

    def __str__(self) -> str:
        return self.batch_identifier


class BatchPlate(TimestampedUUIDModel):
    batch = models.ForeignKey(
        ProcessingBatch,
        on_delete=models.CASCADE,
        related_name="plates",
    )
    layout_template = models.ForeignKey(
        PlateLayoutTemplate,
        on_delete=models.PROTECT,
        related_name="plates",
    )
    plate_identifier = models.CharField(max_length=100, unique=True)
    sequence_number = models.PositiveIntegerField(default=1)
    label = models.CharField(max_length=100, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["batch__batch_identifier", "sequence_number"]
        indexes = [
            models.Index(fields=["batch", "sequence_number"], name="lims_batch_plate_seq_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["batch", "sequence_number"], name="uniq_lims_batch_plate_seq"),
        ]

    def clean(self) -> None:
        super().clean()
        if not isinstance(self.metadata, dict):
            raise ValidationError({"metadata": "metadata must be an object"})

    def __str__(self) -> str:
        return self.plate_identifier


class BatchPlateAssignment(TimestampedUUIDModel):
    plate = models.ForeignKey(
        BatchPlate,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    biospecimen = models.ForeignKey(
        Biospecimen,
        on_delete=models.PROTECT,
        related_name="plate_assignments",
    )
    position_index = models.PositiveIntegerField(default=1)
    well_label = models.CharField(max_length=8)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["plate__plate_identifier", "position_index"]
        constraints = [
            models.UniqueConstraint(fields=["plate", "position_index"], name="uniq_lims_plate_assign_pos"),
            models.UniqueConstraint(fields=["plate", "well_label"], name="uniq_lims_plate_assign_label"),
            models.UniqueConstraint(fields=["plate", "biospecimen"], name="uniq_lims_plate_assign_spec"),
        ]

    def clean(self) -> None:
        super().clean()
        if not isinstance(self.metadata, dict):
            raise ValidationError({"metadata": "metadata must be an object"})
        if self.well_label:
            self.well_label = self.well_label.strip().upper()
        if not self.well_label:
            raise ValidationError({"well_label": "well_label is required"})
        if self.plate_id and self.position_index:
            capacity = self.plate.layout_template.rows * self.plate.layout_template.columns
            if self.position_index < 1 or self.position_index > capacity:
                raise ValidationError({"position_index": "position_index is out of range for the selected layout"})
        if self.plate_id and self.biospecimen_id and self.plate.batch.sample_type_id != self.biospecimen.sample_type_id:
            raise ValidationError({"biospecimen": "biospecimen sample type must match the batch sample type"})

    def __str__(self) -> str:
        return f"{self.plate.plate_identifier}:{self.well_label}"

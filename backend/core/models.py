import uuid

from django.db import models


class Project(models.Model):
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name

class DataAsset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    qualified_name = models.CharField(max_length=512, unique=True)
    display_name = models.CharField(max_length=200)
    asset_type = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')
    owner = models.CharField(max_length=200, blank=True, default='')
    tags = models.JSONField(default=list, blank=True)
    classifications = models.JSONField(default=list, blank=True)
    properties = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.qualified_name


class IngestionRequest(models.Model):
    class Status(models.TextChoices):
        QUEUED = 'queued'
        RUNNING = 'running'
        COMPLETED = 'completed'
        FAILED = 'failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connector = models.CharField(max_length=100)
    source = models.JSONField(default=dict, blank=True)
    mode = models.CharField(max_length=32, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.QUEUED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class LineageEdge(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_asset = models.ForeignKey(DataAsset, on_delete=models.CASCADE, related_name='outgoing_edges')
    to_asset = models.ForeignKey(DataAsset, on_delete=models.CASCADE, related_name='incoming_edges')
    edge_type = models.CharField(max_length=100)
    properties = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['from_asset', 'to_asset', 'edge_type'], name='uniq_lineage_edge'),
        ]


class QualityRule(models.Model):
    class Severity(models.TextChoices):
        WARNING = 'warning'
        ERROR = 'error'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(DataAsset, on_delete=models.CASCADE, related_name='quality_rules')
    rule_type = models.CharField(max_length=100)
    params = models.JSONField(default=dict, blank=True)
    severity = models.CharField(max_length=16, choices=Severity.choices, default=Severity.WARNING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class QualityCheckResult(models.Model):
    class Status(models.TextChoices):
        PASS = 'pass'
        WARN = 'warn'
        FAIL = 'fail'
        ERROR = 'error'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule = models.ForeignKey(QualityRule, on_delete=models.CASCADE, related_name='results')
    status = models.CharField(max_length=16, choices=Status.choices)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class DataContract(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft'
        ACTIVE = 'active'
        DEPRECATED = 'deprecated'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(DataAsset, on_delete=models.CASCADE, related_name='contracts')
    version = models.IntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    schema = models.JSONField(default=dict, blank=True)
    expectations = models.JSONField(default=list, blank=True)
    owners = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['asset', 'version'], name='uniq_contract_asset_version'),
        ]


class RetentionRule(models.Model):
    class Action(models.TextChoices):
        ARCHIVE = 'archive'
        DELETE = 'delete'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scope = models.JSONField(default=dict, blank=True)
    action = models.CharField(max_length=16, choices=Action.choices)
    retention_period = models.CharField(max_length=32)
    grace_period = models.CharField(max_length=32, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class RetentionHold(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(DataAsset, on_delete=models.CASCADE, related_name='retention_holds')
    reason = models.CharField(max_length=512, blank=True, default='')
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    released_at = models.DateTimeField(null=True, blank=True)


class RetentionRun(models.Model):
    class Mode(models.TextChoices):
        DRY_RUN = 'dry_run'
        EXECUTE = 'execute'

    class Status(models.TextChoices):
        STARTED = 'started'
        COMPLETED = 'completed'
        FAILED = 'failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule = models.ForeignKey(RetentionRule, on_delete=models.CASCADE, related_name='runs')
    mode = models.CharField(max_length=16, choices=Mode.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.STARTED)
    summary = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class PrivacyProfile(models.Model):
    class LawfulBasis(models.TextChoices):
        CONTRACT = 'contract'
        LEGAL_OBLIGATION = 'legal_obligation'
        CONSENT = 'consent'
        LEGITIMATE_INTEREST = 'legitimate_interest'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    lawful_basis = models.CharField(max_length=32, choices=LawfulBasis.choices)
    consent_required = models.BooleanField(default=False)
    consent_state = models.CharField(max_length=16, default='unknown')
    privacy_flags = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ConsentEvent(models.Model):
    class ConsentState(models.TextChoices):
        UNKNOWN = 'unknown'
        GRANTED = 'granted'
        WITHDRAWN = 'withdrawn'
        EXPIRED = 'expired'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(PrivacyProfile, on_delete=models.CASCADE, related_name='consent_events')
    consent_state = models.CharField(max_length=16, choices=ConsentState.choices)
    reason = models.CharField(max_length=512, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)


class ResidencyProfile(models.Model):
    class EnforcementMode(models.TextChoices):
        ADVISORY = 'advisory'
        ENFORCED = 'enforced'

    class Status(models.TextChoices):
        DRAFT = 'draft'
        ACTIVE = 'active'
        DEPRECATED = 'deprecated'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    allowed_regions = models.JSONField(default=list, blank=True)
    blocked_regions = models.JSONField(default=list, blank=True)
    enforcement_mode = models.CharField(max_length=16, choices=EnforcementMode.choices, default=EnforcementMode.ADVISORY)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class AccessRequest(models.Model):
    class AccessType(models.TextChoices):
        READ = 'read'
        WRITE = 'write'
        ADMIN = 'admin'
        EXPORT = 'export'

    class Status(models.TextChoices):
        SUBMITTED = 'submitted'
        IN_REVIEW = 'in_review'
        APPROVED = 'approved'
        DENIED = 'denied'
        EXPIRED = 'expired'
        REVOKED = 'revoked'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject_ref = models.CharField(max_length=512)
    requester = models.CharField(max_length=200)
    access_type = models.CharField(max_length=16, choices=AccessType.choices)
    justification = models.TextField(blank=True, default='')
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SUBMITTED)
    approver = models.CharField(max_length=200, blank=True, default='')
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ReferenceDataset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    owner = models.CharField(max_length=200, blank=True, default='')
    domain = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['name'], name='uniq_reference_dataset_name'),
        ]


class ReferenceDatasetVersion(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft'
        APPROVED = 'approved'
        ACTIVE = 'active'
        DEPRECATED = 'deprecated'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(ReferenceDataset, on_delete=models.CASCADE, related_name='versions')
    version = models.IntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    values = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['dataset', 'version'], name='uniq_reference_dataset_version'),
        ]


class MasterRecord(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft'
        ACTIVE = 'active'
        SUPERSEDED = 'superseded'
        ARCHIVED = 'archived'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entity_type = models.CharField(max_length=100)
    master_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    version = models.IntegerField(default=1)
    attributes = models.JSONField(default=dict, blank=True)
    survivorship_policy = models.JSONField(default=dict, blank=True)
    confidence = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['entity_type', 'master_id', 'version'], name='uniq_master_record_version'),
        ]


class MasterMergeCandidate(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending'
        APPROVED = 'approved'
        REJECTED = 'rejected'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entity_type = models.CharField(max_length=100)
    target_master_id = models.UUIDField(db_index=True)
    source_master_refs = models.JSONField(default=list, blank=True)
    proposed_attributes = models.JSONField(default=dict, blank=True)
    confidence = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    approved_by = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Classification(models.Model):
    class Level(models.TextChoices):
        PUBLIC = 'public'
        INTERNAL = 'internal'
        CONFIDENTIAL = 'confidential'
        RESTRICTED = 'restricted'

    class Status(models.TextChoices):
        DRAFT = 'draft'
        ACTIVE = 'active'
        DEPRECATED = 'deprecated'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    level = models.CharField(max_length=16, choices=Level.choices)
    description = models.CharField(max_length=512, blank=True, default='')
    tags = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['name'], name='uniq_classification_name'),
        ]


class PrintJob(models.Model):
    class Format(models.TextChoices):
        ZPL = 'zpl'
        PDF = 'pdf'

    class Status(models.TextChoices):
        PENDING = 'pending'
        RETRYING = 'retrying'
        COMPLETED = 'completed'
        FAILED = 'failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template_ref = models.CharField(max_length=256)
    payload = models.JSONField(default=dict, blank=True)
    output_format = models.CharField(max_length=16, choices=Format.choices)
    destination = models.CharField(max_length=200)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    retry_count = models.IntegerField(default=0)
    gateway_metadata = models.JSONField(default=dict, blank=True)
    error_message = models.CharField(max_length=512, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class CollaborationDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    object_key = models.CharField(max_length=512)
    content_type = models.CharField(max_length=100, blank=True, default='')
    owner = models.CharField(max_length=200, blank=True, default='')
    status = models.CharField(max_length=16, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['object_key'], name='uniq_collaboration_object_key'),
        ]


class CollaborationDocumentVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(CollaborationDocument, on_delete=models.CASCADE, related_name='versions')
    version = models.IntegerField()
    object_key = models.CharField(max_length=512)
    summary = models.CharField(max_length=512, blank=True, default='')
    editor = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['document', 'version'], name='uniq_collaboration_doc_version'),
        ]

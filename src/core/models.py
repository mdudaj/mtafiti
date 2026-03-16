import uuid

from django.db import models


class Project(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=64, blank=True, default="")
    institution_ref = models.CharField(max_length=200, blank=True, default="")
    sync_config = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, default="active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "-created_at"], name="project_status_created_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class ProjectWorkspace(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.OneToOneField(
        Project, on_delete=models.CASCADE, related_name="workspace"
    )
    collaboration_enabled = models.BooleanField(default=True)
    data_management_enabled = models.BooleanField(default=True)
    document_management_enabled = models.BooleanField(default=True)
    collaboration_tools = models.JSONField(default=list, blank=True)
    data_resources = models.JSONField(default=list, blank=True)
    documents = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ProjectMembership(models.Model):
    class Role(models.TextChoices):
        PRINCIPAL_INVESTIGATOR = "principal_investigator"
        RESEARCHER = "researcher"
        DATA_MANAGER = "data_manager"

    class Status(models.TextChoices):
        ACTIVE = "active"
        INACTIVE = "inactive"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="memberships"
    )
    user_email = models.EmailField(max_length=320)
    role = models.CharField(max_length=64, choices=Role.choices)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE
    )
    invited_by = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "user_email"], name="uniq_project_member_email"
            ),
        ]
        indexes = [
            models.Index(fields=["project", "status", "-created_at"], name="proj_member_list_idx"),
        ]


class ProjectInvitation(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        ACCEPTED = "accepted"
        EXPIRED = "expired"
        REVOKED = "revoked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="invitations"
    )
    email = models.EmailField(max_length=320)
    role = models.CharField(max_length=64, choices=ProjectMembership.Role.choices)
    token = models.CharField(max_length=64, unique=True)
    token_attempts = models.PositiveIntegerField(default=0)
    max_token_attempts = models.PositiveIntegerField(default=5)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING
    )
    invited_by = models.CharField(max_length=200, blank=True, default="")
    accepted_by = models.CharField(max_length=200, blank=True, default="")
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    resent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class UserNotification(models.Model):
    class Channel(models.TextChoices):
        IN_APP = "in_app"
        EMAIL = "email"
        WEBHOOK = "webhook"

    class DeliveryStatus(models.TextChoices):
        PENDING = "pending"
        SENT = "sent"
        FAILED = "failed"
        DEAD_LETTER = "dead_letter"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_email = models.EmailField(max_length=320)
    notification_type = models.CharField(max_length=64)
    channel = models.CharField(max_length=16, choices=Channel.choices)
    payload = models.JSONField(default=dict, blank=True)
    provider = models.CharField(max_length=32, default="default")
    delivery_status = models.CharField(
        max_length=16, choices=DeliveryStatus.choices, default=DeliveryStatus.PENDING
    )
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    dead_lettered_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=512, blank=True, default="")
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["delivery_status", "next_attempt_at", "-created_at"],
                name="notif_queue_scan_idx",
            ),
            models.Index(fields=["user_email", "-created_at"], name="notif_user_created_idx"),
        ]


class UserProfile(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active"
        INVITED = "invited"
        DISABLED = "disabled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=320, unique=True)
    display_name = models.CharField(max_length=200, blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    last_login_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ProjectMembershipRoleHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    membership = models.ForeignKey(
        ProjectMembership, on_delete=models.CASCADE, related_name="role_history"
    )
    action = models.CharField(max_length=32)
    previous_role = models.CharField(max_length=64, blank=True, default="")
    new_role = models.CharField(max_length=64, blank=True, default="")
    previous_status = models.CharField(max_length=16, blank=True, default="")
    new_status = models.CharField(max_length=16, blank=True, default="")
    actor_id = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)


class DataAsset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    qualified_name = models.CharField(max_length=512, unique=True)
    display_name = models.CharField(max_length=200)
    asset_type = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")
    owner = models.CharField(max_length=200, blank=True, default="")
    tags = models.JSONField(default=list, blank=True)
    classifications = models.JSONField(default=list, blank=True)
    properties = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.qualified_name


class IngestionRequest(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued"
        RUNNING = "running"
        COMPLETED = "completed"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="ingestions"
    )
    connector = models.CharField(max_length=100)
    source = models.JSONField(default=dict, blank=True)
    mode = models.CharField(max_length=32, blank=True)
    status = models.CharField(
        max_length=32, choices=Status.choices, default=Status.QUEUED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["project", "status", "-created_at"], name="ingest_proj_status_idx"),
        ]


class LineageEdge(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_asset = models.ForeignKey(
        DataAsset, on_delete=models.CASCADE, related_name="outgoing_edges"
    )
    to_asset = models.ForeignKey(
        DataAsset, on_delete=models.CASCADE, related_name="incoming_edges"
    )
    edge_type = models.CharField(max_length=100)
    properties = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["from_asset", "to_asset", "edge_type"], name="uniq_lineage_edge"
            ),
        ]


class QualityRule(models.Model):
    class Severity(models.TextChoices):
        WARNING = "warning"
        ERROR = "error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(
        DataAsset, on_delete=models.CASCADE, related_name="quality_rules"
    )
    rule_type = models.CharField(max_length=100)
    params = models.JSONField(default=dict, blank=True)
    severity = models.CharField(
        max_length=16, choices=Severity.choices, default=Severity.WARNING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class QualityCheckResult(models.Model):
    class Status(models.TextChoices):
        PASS = "pass"
        WARN = "warn"
        FAIL = "fail"
        ERROR = "error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule = models.ForeignKey(
        QualityRule, on_delete=models.CASCADE, related_name="results"
    )
    status = models.CharField(max_length=16, choices=Status.choices)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class DataContract(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft"
        ACTIVE = "active"
        DEPRECATED = "deprecated"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(
        DataAsset, on_delete=models.CASCADE, related_name="contracts"
    )
    version = models.IntegerField()
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT
    )
    schema = models.JSONField(default=dict, blank=True)
    expectations = models.JSONField(default=list, blank=True)
    owners = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "version"], name="uniq_contract_asset_version"
            ),
        ]


class AssetVersion(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft"
        PUBLISHED = "published"
        SUPERSEDED = "superseded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(
        DataAsset, on_delete=models.CASCADE, related_name="versions"
    )
    version_number = models.IntegerField()
    change_summary = models.CharField(max_length=512, blank=True, default="")
    change_set = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT
    )
    created_by = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "version_number"], name="uniq_asset_version_number"
            ),
        ]


class RetentionRule(models.Model):
    class Action(models.TextChoices):
        ARCHIVE = "archive"
        DELETE = "delete"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scope = models.JSONField(default=dict, blank=True)
    action = models.CharField(max_length=16, choices=Action.choices)
    retention_period = models.CharField(max_length=32)
    grace_period = models.CharField(max_length=32, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class RetentionHold(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(
        DataAsset, on_delete=models.CASCADE, related_name="retention_holds"
    )
    reason = models.CharField(max_length=512, blank=True, default="")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    released_at = models.DateTimeField(null=True, blank=True)


class RetentionRun(models.Model):
    class Mode(models.TextChoices):
        DRY_RUN = "dry_run"
        EXECUTE = "execute"

    class Status(models.TextChoices):
        STARTED = "started"
        COMPLETED = "completed"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule = models.ForeignKey(
        RetentionRule, on_delete=models.CASCADE, related_name="runs"
    )
    mode = models.CharField(max_length=16, choices=Mode.choices)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.STARTED
    )
    summary = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class PrivacyProfile(models.Model):
    class LawfulBasis(models.TextChoices):
        CONTRACT = "contract"
        LEGAL_OBLIGATION = "legal_obligation"
        CONSENT = "consent"
        LEGITIMATE_INTEREST = "legitimate_interest"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    lawful_basis = models.CharField(max_length=32, choices=LawfulBasis.choices)
    consent_required = models.BooleanField(default=False)
    consent_state = models.CharField(max_length=16, default="unknown")
    privacy_flags = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ConsentEvent(models.Model):
    class ConsentState(models.TextChoices):
        UNKNOWN = "unknown"
        GRANTED = "granted"
        WITHDRAWN = "withdrawn"
        EXPIRED = "expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        PrivacyProfile, on_delete=models.CASCADE, related_name="consent_events"
    )
    consent_state = models.CharField(max_length=16, choices=ConsentState.choices)
    reason = models.CharField(max_length=512, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)


class PrivacyAction(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested"
        APPROVED = "approved"
        REJECTED = "rejected"
        EXECUTED = "executed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        PrivacyProfile, on_delete=models.CASCADE, related_name="actions"
    )
    action_type = models.CharField(max_length=64)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.REQUESTED
    )
    reason = models.CharField(max_length=512, blank=True, default="")
    actor_id = models.CharField(max_length=200, blank=True, default="")
    evidence = models.JSONField(default=dict, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)


class AgentRun(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued"
        RUNNING = "running"
        COMPLETED = "completed"
        FAILED = "failed"
        CANCELLED = "cancelled"
        TIMED_OUT = "timed_out"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor_id = models.CharField(max_length=200, blank=True, default="")
    prompt = models.TextField(blank=True, default="")
    allowed_tools = models.JSONField(default=list, blank=True)
    timeout_seconds = models.IntegerField(default=60)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.QUEUED
    )
    output = models.JSONField(default=dict, blank=True)
    error_message = models.CharField(max_length=512, blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class StewardshipItem(models.Model):
    class ItemType(models.TextChoices):
        QUALITY_EXCEPTION = "quality_exception"
        CONTRACT_VIOLATION = "contract_violation"
        RETENTION_HOLD = "retention_hold"
        GLOSSARY_REVIEW = "glossary_review"
        MDM_MERGE_REVIEW = "mdm_merge_review"

    class Severity(models.TextChoices):
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"
        CRITICAL = "critical"

    class Status(models.TextChoices):
        OPEN = "open"
        IN_REVIEW = "in_review"
        BLOCKED = "blocked"
        RESOLVED = "resolved"
        DISMISSED = "dismissed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item_type = models.CharField(max_length=32, choices=ItemType.choices)
    subject_ref = models.CharField(max_length=512)
    severity = models.CharField(
        max_length=16, choices=Severity.choices, default=Severity.MEDIUM
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    assignee = models.CharField(max_length=200, blank=True, default="")
    due_at = models.DateTimeField(null=True, blank=True)
    resolution = models.JSONField(default=dict, blank=True)
    actor_id = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)


class ResidencyProfile(models.Model):
    class EnforcementMode(models.TextChoices):
        ADVISORY = "advisory"
        ENFORCED = "enforced"

    class Status(models.TextChoices):
        DRAFT = "draft"
        ACTIVE = "active"
        DEPRECATED = "deprecated"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    allowed_regions = models.JSONField(default=list, blank=True)
    blocked_regions = models.JSONField(default=list, blank=True)
    enforcement_mode = models.CharField(
        max_length=16, choices=EnforcementMode.choices, default=EnforcementMode.ADVISORY
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class AccessRequest(models.Model):
    class AccessType(models.TextChoices):
        READ = "read"
        WRITE = "write"
        ADMIN = "admin"
        EXPORT = "export"

    class Status(models.TextChoices):
        SUBMITTED = "submitted"
        IN_REVIEW = "in_review"
        APPROVED = "approved"
        DENIED = "denied"
        EXPIRED = "expired"
        REVOKED = "revoked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject_ref = models.CharField(max_length=512)
    requester = models.CharField(max_length=200)
    access_type = models.CharField(max_length=16, choices=AccessType.choices)
    justification = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.SUBMITTED
    )
    approver = models.CharField(max_length=200, blank=True, default="")
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ReferenceDataset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    owner = models.CharField(max_length=200, blank=True, default="")
    domain = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name"], name="uniq_reference_dataset_name"
            ),
        ]


class ReferenceDatasetVersion(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft"
        APPROVED = "approved"
        ACTIVE = "active"
        DEPRECATED = "deprecated"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(
        ReferenceDataset, on_delete=models.CASCADE, related_name="versions"
    )
    version = models.IntegerField()
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT
    )
    values = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["dataset", "version"], name="uniq_reference_dataset_version"
            ),
        ]


class MasterRecord(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft"
        ACTIVE = "active"
        SUPERSEDED = "superseded"
        ARCHIVED = "archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entity_type = models.CharField(max_length=100)
    master_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    version = models.IntegerField(default=1)
    attributes = models.JSONField(default=dict, blank=True)
    survivorship_policy = models.JSONField(default=dict, blank=True)
    confidence = models.FloatField(null=True, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["entity_type", "master_id", "version"],
                name="uniq_master_record_version",
            ),
        ]


class MasterMergeCandidate(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        APPROVED = "approved"
        REJECTED = "rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entity_type = models.CharField(max_length=100)
    target_master_id = models.UUIDField(db_index=True)
    source_master_refs = models.JSONField(default=list, blank=True)
    proposed_attributes = models.JSONField(default=dict, blank=True)
    confidence = models.FloatField(null=True, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING
    )
    approved_by = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Classification(models.Model):
    class Level(models.TextChoices):
        PUBLIC = "public"
        INTERNAL = "internal"
        CONFIDENTIAL = "confidential"
        RESTRICTED = "restricted"

    class Status(models.TextChoices):
        DRAFT = "draft"
        ACTIVE = "active"
        DEPRECATED = "deprecated"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    level = models.CharField(max_length=16, choices=Level.choices)
    description = models.CharField(max_length=512, blank=True, default="")
    tags = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["name"], name="uniq_classification_name"),
        ]


class PrintJob(models.Model):
    class Format(models.TextChoices):
        ZPL = "zpl"
        PDF = "pdf"

    class Status(models.TextChoices):
        PENDING = "pending"
        RETRYING = "retrying"
        COMPLETED = "completed"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template_ref = models.CharField(max_length=256)
    payload = models.JSONField(default=dict, blank=True)
    output_format = models.CharField(max_length=16, choices=Format.choices)
    destination = models.CharField(max_length=200)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING
    )
    retry_count = models.IntegerField(default=0)
    gateway_metadata = models.JSONField(default=dict, blank=True)
    error_message = models.CharField(max_length=512, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class PrintGateway(models.Model):
    class Status(models.TextChoices):
        ONLINE = "online"
        OFFLINE = "offline"
        DEGRADED = "degraded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gateway_ref = models.CharField(max_length=128, unique=True)
    display_name = models.CharField(max_length=200)
    site_ref = models.CharField(max_length=200, blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OFFLINE)
    capabilities = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    last_seen_version = models.CharField(max_length=64, blank=True, default="")
    last_heartbeat_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "-updated_at"], name="print_gateway_status_idx"),
        ]


class PrintTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    template_ref = models.CharField(max_length=256, unique=True)
    output_format = models.CharField(max_length=16, choices=PrintJob.Format.choices)
    content = models.TextField(blank=True, default="")
    sample_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["-updated_at"], name="print_template_updated_idx"),
        ]


class CollaborationDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    object_key = models.CharField(max_length=512)
    content_type = models.CharField(max_length=100, blank=True, default="")
    owner = models.CharField(max_length=200, blank=True, default="")
    status = models.CharField(max_length=16, default="active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["object_key"], name="uniq_collaboration_object_key"
            ),
        ]


class CollaborationDocumentVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        CollaborationDocument, on_delete=models.CASCADE, related_name="versions"
    )
    version = models.IntegerField()
    object_key = models.CharField(max_length=512)
    summary = models.CharField(max_length=512, blank=True, default="")
    editor = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["document", "version"], name="uniq_collaboration_doc_version"
            ),
        ]


class NotebookWorkspace(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    owner = models.CharField(max_length=200, blank=True, default="")
    image = models.CharField(max_length=256, blank=True, default="")
    cpu_limit = models.CharField(max_length=32, blank=True, default="")
    memory_limit = models.CharField(max_length=32, blank=True, default="")
    storage_mounts = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=16, default="active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name"], name="uniq_notebook_workspace_name"
            ),
        ]


class NotebookSession(models.Model):
    class Status(models.TextChoices):
        STARTED = "started"
        TERMINATED = "terminated"
        RESOURCE_LIMITED = "resource_limited"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        NotebookWorkspace, on_delete=models.CASCADE, related_name="sessions"
    )
    user_id = models.CharField(max_length=200, blank=True, default="")
    pod_name = models.CharField(max_length=200, blank=True, default="")
    status = models.CharField(
        max_length=32, choices=Status.choices, default=Status.STARTED
    )
    metadata = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)


class NotebookExecution(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested"
        COMPLETED = "completed"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        NotebookSession, on_delete=models.CASCADE, related_name="executions"
    )
    cell_ref = models.CharField(max_length=200, blank=True, default="")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.REQUESTED
    )
    metadata = models.JSONField(default=dict, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class ConnectorRun(models.Model):
    class ExecutionPath(models.TextChoices):
        WORKER = "worker"
        JOB = "job"

    class Status(models.TextChoices):
        QUEUED = "queued"
        RUNNING = "running"
        SUCCEEDED = "succeeded"
        FAILED = "failed"
        CANCELLED = "cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ingestion = models.ForeignKey(
        IngestionRequest, on_delete=models.CASCADE, related_name="connector_runs"
    )
    execution_path = models.CharField(
        max_length=16, choices=ExecutionPath.choices, default=ExecutionPath.WORKER
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.QUEUED
    )
    retry_count = models.IntegerField(default=0)
    progress = models.JSONField(default=dict, blank=True)
    error_message = models.CharField(max_length=512, blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "-created_at"], name="connector_status_created_idx"),
            models.Index(fields=["ingestion", "status", "-created_at"], name="connector_ingest_status_idx"),
        ]


class WorkflowDefinition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.CharField(max_length=512, blank=True, default="")
    domain_ref = models.CharField(max_length=256, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["name"], name="uniq_workflow_definition_name")
        ]


class WorkflowRun(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft"
        IN_REVIEW = "in_review"
        APPROVED = "approved"
        ACTIVE = "active"
        SUPERSEDED = "superseded"
        ROLLED_BACK = "rolled_back"
        REJECTED = "rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    definition = models.ForeignKey(
        WorkflowDefinition, on_delete=models.CASCADE, related_name="runs"
    )
    subject_ref = models.CharField(max_length=256, blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    submitted_by = models.CharField(max_length=200, blank=True, default="")
    reviewed_by = models.CharField(max_length=200, blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class WorkflowTask(models.Model):
    class Status(models.TextChoices):
        OPEN = "open"
        COMPLETED = "completed"
        CANCELLED = "cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(WorkflowRun, on_delete=models.CASCADE, related_name="tasks")
    task_type = models.CharField(max_length=64)
    assignee = models.CharField(max_length=200, blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class OrchestrationWorkflow(models.Model):
    class TriggerType(models.TextChoices):
        SCHEDULE = "schedule"
        EVENT = "event"

    class Status(models.TextChoices):
        ACTIVE = "active"
        PAUSED = "paused"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="orchestration_workflows"
    )
    name = models.CharField(max_length=200)
    trigger_type = models.CharField(
        max_length=16, choices=TriggerType.choices, default=TriggerType.EVENT
    )
    trigger_value = models.CharField(max_length=200, blank=True, default="")
    steps = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["name"], name="uniq_orchestration_workflow_name")
        ]


class OrchestrationRun(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued"
        RUNNING = "running"
        SUCCEEDED = "succeeded"
        FAILED = "failed"
        CANCELLED = "cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="orchestration_runs"
    )
    workflow = models.ForeignKey(
        OrchestrationWorkflow, on_delete=models.CASCADE, related_name="runs"
    )
    trigger_context = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.QUEUED
    )
    step_results = models.JSONField(default=list, blank=True)
    error_message = models.CharField(max_length=512, blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["project", "status", "-created_at"], name="orch_proj_status_idx"),
            models.Index(fields=["workflow", "status", "-created_at"], name="orch_workflow_status_idx"),
        ]


class GovernancePolicy(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft"
        IN_REVIEW = "in_review"
        APPROVED = "approved"
        ACTIVE = "active"
        SUPERSEDED = "superseded"
        ROLLED_BACK = "rolled_back"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    version = models.IntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    rules = models.JSONField(default=dict, blank=True)
    reason = models.CharField(max_length=512, blank=True, default="")
    actor_id = models.CharField(max_length=200, blank=True, default="")
    rollback_target = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rollback_children",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name", "version"], name="uniq_governance_policy_name_version"
            )
        ]


class GovernancePolicyTransition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    policy = models.ForeignKey(
        GovernancePolicy, on_delete=models.CASCADE, related_name="transitions"
    )
    from_status = models.CharField(max_length=16)
    to_status = models.CharField(max_length=16)
    action = models.CharField(max_length=64)
    reason = models.CharField(max_length=512, blank=True, default="")
    actor_id = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)


class GlossaryTerm(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft"
        APPROVED = "approved"
        DEPRECATED = "deprecated"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    definition = models.TextField(blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    owners = models.JSONField(default=list, blank=True)
    stewards = models.JSONField(default=list, blank=True)
    related_asset_ids = models.JSONField(default=list, blank=True)
    classifications = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["name"], name="uniq_glossary_term_name"),
        ]


class DataProduct(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft"
        ACTIVE = "active"
        RETIRED = "retired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    domain = models.CharField(max_length=200, blank=True, default="")
    owner = models.CharField(max_length=200, blank=True, default="")
    asset_ids = models.JSONField(default=list, blank=True)
    sla = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["name"], name="uniq_data_product_name"),
        ]


class DataShare(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft"
        APPROVED = "approved"
        ACTIVE = "active"
        REVOKED = "revoked"
        EXPIRED = "expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(DataAsset, on_delete=models.CASCADE, related_name="data_shares")
    consumer_ref = models.CharField(max_length=256)
    purpose = models.CharField(max_length=256, blank=True, default="")
    constraints = models.JSONField(default=dict, blank=True)
    linked_access_request_ids = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    expires_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

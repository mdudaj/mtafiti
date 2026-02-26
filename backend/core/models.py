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

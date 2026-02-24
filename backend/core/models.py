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

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0017_notebookworkspace_notebooksession_notebookexecution"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConnectorRun",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "execution_path",
                    models.CharField(
                        choices=[("worker", "Worker"), ("job", "Job")],
                        default="worker",
                        max_length=16,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("running", "Running"),
                            ("succeeded", "Succeeded"),
                            ("failed", "Failed"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="queued",
                        max_length=16,
                    ),
                ),
                ("retry_count", models.IntegerField(default=0)),
                ("progress", models.JSONField(blank=True, default=dict)),
                ("error_message", models.CharField(blank=True, default="", max_length=512)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "ingestion",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="connector_runs",
                        to="core.ingestionrequest",
                    ),
                ),
            ],
        ),
    ]

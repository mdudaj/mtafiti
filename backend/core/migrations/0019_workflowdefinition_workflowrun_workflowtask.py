from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0018_connectorrun"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkflowDefinition",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("name", models.CharField(max_length=200)),
                ("description", models.CharField(blank=True, default="", max_length=512)),
                ("domain_ref", models.CharField(blank=True, default="", max_length=256)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("name",), name="uniq_workflow_definition_name"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="WorkflowRun",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("subject_ref", models.CharField(blank=True, default="", max_length=256)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("in_review", "In Review"),
                            ("approved", "Approved"),
                            ("active", "Active"),
                            ("superseded", "Superseded"),
                            ("rolled_back", "Rolled Back"),
                            ("rejected", "Rejected"),
                        ],
                        default="draft",
                        max_length=16,
                    ),
                ),
                ("submitted_by", models.CharField(blank=True, default="", max_length=200)),
                ("reviewed_by", models.CharField(blank=True, default="", max_length=200)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "definition",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="runs",
                        to="core.workflowdefinition",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="WorkflowTask",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("task_type", models.CharField(max_length=64)),
                ("assignee", models.CharField(blank=True, default="", max_length=200)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("open", "Open"),
                            ("completed", "Completed"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="open",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tasks",
                        to="core.workflowrun",
                    ),
                ),
            ],
        ),
    ]

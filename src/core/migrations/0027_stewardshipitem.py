from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0026_agentrun"),
    ]

    operations = [
        migrations.CreateModel(
            name="StewardshipItem",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "item_type",
                    models.CharField(
                        choices=[
                            ("quality_exception", "Quality Exception"),
                            ("contract_violation", "Contract Violation"),
                            ("retention_hold", "Retention Hold"),
                            ("glossary_review", "Glossary Review"),
                            ("mdm_merge_review", "Mdm Merge Review"),
                        ],
                        max_length=32,
                    ),
                ),
                ("subject_ref", models.CharField(max_length=512)),
                (
                    "severity",
                    models.CharField(
                        choices=[
                            ("low", "Low"),
                            ("medium", "Medium"),
                            ("high", "High"),
                            ("critical", "Critical"),
                        ],
                        default="medium",
                        max_length=16,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("open", "Open"),
                            ("in_review", "In Review"),
                            ("blocked", "Blocked"),
                            ("resolved", "Resolved"),
                            ("dismissed", "Dismissed"),
                        ],
                        default="open",
                        max_length=16,
                    ),
                ),
                ("assignee", models.CharField(blank=True, default="", max_length=200)),
                ("due_at", models.DateTimeField(blank=True, null=True)),
                ("resolution", models.JSONField(blank=True, default=dict)),
                ("actor_id", models.CharField(blank=True, default="", max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
            ],
        ),
    ]

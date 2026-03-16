import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0029_project_scoping_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserNotification",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("user_email", models.EmailField(max_length=320)),
                ("notification_type", models.CharField(max_length=64)),
                ("channel", models.CharField(choices=[("in_app", "In App"), ("email", "Email")], max_length=16)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="ProjectMembership",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("user_email", models.EmailField(max_length=320)),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("principal_investigator", "Principal Investigator"),
                            ("researcher", "Researcher"),
                            ("data_manager", "Data Manager"),
                        ],
                        max_length=64,
                    ),
                ),
                ("status", models.CharField(choices=[("active", "Active"), ("inactive", "Inactive")], default="active", max_length=16)),
                ("invited_by", models.CharField(blank=True, default="", max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "project",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="core.project"),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("project", "user_email"), name="uniq_project_member_email")
                ],
            },
        ),
        migrations.CreateModel(
            name="ProjectInvitation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("email", models.EmailField(max_length=320)),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("principal_investigator", "Principal Investigator"),
                            ("researcher", "Researcher"),
                            ("data_manager", "Data Manager"),
                        ],
                        max_length=64,
                    ),
                ),
                ("token", models.CharField(max_length=64, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("accepted", "Accepted"),
                            ("expired", "Expired"),
                            ("revoked", "Revoked"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("invited_by", models.CharField(blank=True, default="", max_length=200)),
                ("accepted_by", models.CharField(blank=True, default="", max_length=200)),
                ("expires_at", models.DateTimeField()),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "project",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="invitations", to="core.project"),
                ),
            ],
        ),
    ]

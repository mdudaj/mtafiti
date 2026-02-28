import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0030_projectmembership_projectinvitation_usernotification"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserProfile",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("email", models.EmailField(max_length=320, unique=True)),
                ("display_name", models.CharField(blank=True, default="", max_length=200)),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Active"), ("invited", "Invited"), ("disabled", "Disabled")],
                        default="active",
                        max_length=16,
                    ),
                ),
                ("last_login_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="ProjectMembershipRoleHistory",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("action", models.CharField(max_length=32)),
                ("previous_role", models.CharField(blank=True, default="", max_length=64)),
                ("new_role", models.CharField(blank=True, default="", max_length=64)),
                ("previous_status", models.CharField(blank=True, default="", max_length=16)),
                ("new_status", models.CharField(blank=True, default="", max_length=16)),
                ("actor_id", models.CharField(blank=True, default="", max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "membership",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="role_history",
                        to="core.projectmembership",
                    ),
                ),
            ],
        ),
    ]

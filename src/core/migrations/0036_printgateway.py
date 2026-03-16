from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0035_projectworkspace"),
    ]

    operations = [
        migrations.CreateModel(
            name="PrintGateway",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("gateway_ref", models.CharField(max_length=128, unique=True)),
                ("display_name", models.CharField(max_length=200)),
                ("site_ref", models.CharField(blank=True, default="", max_length=200)),
                ("status", models.CharField(choices=[("online", "online"), ("offline", "offline"), ("degraded", "degraded")], default="offline", max_length=16)),
                ("capabilities", models.JSONField(blank=True, default=list)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("last_seen_version", models.CharField(blank=True, default="", max_length=64)),
                ("last_heartbeat_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "indexes": [models.Index(fields=["status", "-updated_at"], name="print_gateway_status_idx")],
            },
        ),
    ]

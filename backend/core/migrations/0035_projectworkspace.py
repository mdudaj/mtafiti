from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0034_scalability_indexes"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectWorkspace",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("collaboration_enabled", models.BooleanField(default=True)),
                ("data_management_enabled", models.BooleanField(default=True)),
                ("document_management_enabled", models.BooleanField(default=True)),
                ("collaboration_tools", models.JSONField(blank=True, default=list)),
                ("data_resources", models.JSONField(blank=True, default=list)),
                ("documents", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("project", models.OneToOneField(on_delete=models.CASCADE, related_name="workspace", to="core.project")),
            ],
        ),
    ]

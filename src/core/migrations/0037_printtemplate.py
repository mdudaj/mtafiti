import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0036_printgateway"),
    ]

    operations = [
        migrations.CreateModel(
            name="PrintTemplate",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=200)),
                ("template_ref", models.CharField(max_length=256, unique=True)),
                ("output_format", models.CharField(choices=[("zpl", "Zpl"), ("pdf", "Pdf")], max_length=16)),
                ("content", models.TextField(blank=True, default="")),
                ("sample_payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "indexes": [models.Index(fields=["-updated_at"], name="print_template_updated_idx")],
            },
        ),
    ]

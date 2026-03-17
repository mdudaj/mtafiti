import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Lab",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200)),
                ("code", models.CharField(blank=True, default="", max_length=64)),
                ("description", models.TextField(blank=True, default="")),
                ("address_line", models.CharField(blank=True, default="", max_length=255)),
                ("postcode", models.CharField(blank=True, default="", max_length=16)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["name"],
                "indexes": [
                    models.Index(fields=["name"], name="lims_lab_name_idx"),
                    models.Index(fields=["code"], name="lims_lab_code_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="Study",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200)),
                ("code", models.CharField(blank=True, default="", max_length=64)),
                ("description", models.TextField(blank=True, default="")),
                ("sponsor", models.CharField(blank=True, default="", max_length=200)),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Active"), ("paused", "Paused"), ("completed", "Completed")],
                        default="active",
                        max_length=16,
                    ),
                ),
                (
                    "lead_lab",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="lead_studies",
                        to="lims.lab",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
                "indexes": [
                    models.Index(fields=["name"], name="lims_study_name_idx"),
                    models.Index(fields=["code"], name="lims_study_code_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="TanzaniaAddressSyncRun",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "mode",
                    models.CharField(
                        choices=[("full_refresh", "Full Refresh"), ("incremental", "Incremental")],
                        default="incremental",
                        max_length=24,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("running", "Running"),
                            ("paused", "Paused"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("source_root", models.URLField(default="https://www.tanzaniapostcode.com/", max_length=800)),
                ("checkpoint", models.JSONField(blank=True, default=dict)),
                ("stats", models.JSONField(blank=True, default=dict)),
                ("request_budget", models.PositiveIntegerField(default=10)),
                ("throttle_seconds", models.PositiveIntegerField(default=2)),
                ("pages_processed", models.PositiveIntegerField(default=0)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("next_not_before_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True, default="")),
                ("triggered_by", models.CharField(blank=True, default="", max_length=200)),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [models.Index(fields=["status", "-created_at"], name="lims_addr_sync_status_idx")],
            },
        ),
        migrations.CreateModel(
            name="TanzaniaRegion",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200, unique=True)),
                ("slug", models.SlugField(blank=True, default="", max_length=220)),
                ("source_path", models.CharField(max_length=500, unique=True)),
                ("source_url", models.URLField(max_length=800)),
                ("is_active", models.BooleanField(default=True)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="TanzaniaDistrict",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200)),
                ("slug", models.SlugField(blank=True, default="", max_length=220)),
                ("source_path", models.CharField(max_length=500, unique=True)),
                ("source_url", models.URLField(max_length=800)),
                ("is_active", models.BooleanField(default=True)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                (
                    "region",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="districts",
                        to="lims.tanzaniaregion",
                    ),
                ),
            ],
            options={"ordering": ["region__name", "name"]},
        ),
        migrations.CreateModel(
            name="TanzaniaWard",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200)),
                ("slug", models.SlugField(blank=True, default="", max_length=220)),
                ("source_path", models.CharField(max_length=500, unique=True)),
                ("source_url", models.URLField(max_length=800)),
                ("is_active", models.BooleanField(default=True)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                (
                    "district",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="wards",
                        to="lims.tanzaniadistrict",
                    ),
                ),
            ],
            options={"ordering": ["district__region__name", "district__name", "name"]},
        ),
        migrations.CreateModel(
            name="TanzaniaStreet",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200)),
                ("slug", models.SlugField(blank=True, default="", max_length=220)),
                ("source_path", models.CharField(max_length=500, unique=True)),
                ("source_url", models.URLField(max_length=800)),
                ("postcode", models.CharField(blank=True, default="", max_length=16)),
                ("is_active", models.BooleanField(default=True)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                (
                    "ward",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="streets",
                        to="lims.tanzaniaward",
                    ),
                ),
            ],
            options={"ordering": ["ward__district__region__name", "ward__district__name", "ward__name", "name"]},
        ),
        migrations.CreateModel(
            name="Site",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200)),
                ("code", models.CharField(blank=True, default="", max_length=64)),
                ("description", models.TextField(blank=True, default="")),
                ("address_line", models.CharField(blank=True, default="", max_length=255)),
                ("postcode", models.CharField(blank=True, default="", max_length=16)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "district",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sites", to="lims.tanzaniadistrict"),
                ),
                (
                    "lab",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sites", to="lims.lab"),
                ),
                (
                    "region",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sites", to="lims.tanzaniaregion"),
                ),
                (
                    "street",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sites", to="lims.tanzaniastreet"),
                ),
                (
                    "study",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sites", to="lims.study"),
                ),
                (
                    "ward",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sites", to="lims.tanzaniaward"),
                ),
            ],
            options={
                "ordering": ["name"],
                "indexes": [
                    models.Index(fields=["name"], name="lims_site_name_idx"),
                    models.Index(fields=["code"], name="lims_site_code_idx"),
                ],
            },
        ),
        migrations.AddField(
            model_name="lab",
            name="district",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="labs", to="lims.tanzaniadistrict"),
        ),
        migrations.AddField(
            model_name="lab",
            name="region",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="labs", to="lims.tanzaniaregion"),
        ),
        migrations.AddField(
            model_name="lab",
            name="street",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="labs", to="lims.tanzaniastreet"),
        ),
        migrations.AddField(
            model_name="lab",
            name="ward",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="labs", to="lims.tanzaniaward"),
        ),
        migrations.AddConstraint(
            model_name="tanzaniadistrict",
            constraint=models.UniqueConstraint(fields=("region", "name"), name="uniq_lims_tz_district_per_region"),
        ),
        migrations.AddConstraint(
            model_name="tanzaniastreet",
            constraint=models.UniqueConstraint(fields=("ward", "name"), name="uniq_lims_tz_street_per_ward"),
        ),
        migrations.AddConstraint(
            model_name="tanzaniaward",
            constraint=models.UniqueConstraint(fields=("district", "name"), name="uniq_lims_tz_ward_per_district"),
        ),
    ]

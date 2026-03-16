from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0028_orchestrationworkflow_orchestrationrun"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="code",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="project",
            name="institution_ref",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AddField(
            model_name="project",
            name="status",
            field=models.CharField(default="active", max_length=16),
        ),
        migrations.AddField(
            model_name="project",
            name="sync_config",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="project",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="ingestionrequest",
            name="project",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ingestions",
                to="core.project",
            ),
        ),
        migrations.AddField(
            model_name="orchestrationworkflow",
            name="project",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="orchestration_workflows",
                to="core.project",
            ),
        ),
        migrations.AddField(
            model_name="orchestrationrun",
            name="project",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="orchestration_runs",
                to="core.project",
            ),
        ),
    ]

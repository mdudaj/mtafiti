from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0033_projectinvitation_security_fields"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="project",
            index=models.Index(fields=["status", "-created_at"], name="project_status_created_idx"),
        ),
        migrations.AddIndex(
            model_name="projectmembership",
            index=models.Index(fields=["project", "status", "-created_at"], name="proj_member_list_idx"),
        ),
        migrations.AddIndex(
            model_name="usernotification",
            index=models.Index(
                fields=["delivery_status", "next_attempt_at", "-created_at"],
                name="notif_queue_scan_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="usernotification",
            index=models.Index(fields=["user_email", "-created_at"], name="notif_user_created_idx"),
        ),
        migrations.AddIndex(
            model_name="ingestionrequest",
            index=models.Index(fields=["project", "status", "-created_at"], name="ingest_proj_status_idx"),
        ),
        migrations.AddIndex(
            model_name="connectorrun",
            index=models.Index(fields=["status", "-created_at"], name="connector_status_created_idx"),
        ),
        migrations.AddIndex(
            model_name="connectorrun",
            index=models.Index(fields=["ingestion", "status", "-created_at"], name="connector_ingest_status_idx"),
        ),
        migrations.AddIndex(
            model_name="orchestrationrun",
            index=models.Index(fields=["project", "status", "-created_at"], name="orch_proj_status_idx"),
        ),
        migrations.AddIndex(
            model_name="orchestrationrun",
            index=models.Index(fields=["workflow", "status", "-created_at"], name="orch_workflow_status_idx"),
        ),
    ]

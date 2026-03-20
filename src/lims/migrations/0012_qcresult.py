import uuid
import django.db.models.deletion
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("lims", "0011_operationdefinition_operationversion_operationrun_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="QCResult",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("decision", models.CharField(choices=[("accept", "Accept"), ("reject", "Reject")], max_length=16)),
                ("notes", models.TextField(blank=True, default="")),
                ("rejection_code", models.CharField(blank=True, default="", max_length=32)),
                ("recorded_by", models.CharField(blank=True, default="", max_length=200)),
                ("reviewed_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "discrepancy",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="qc_results",
                        to="lims.receivingdiscrepancy",
                    ),
                ),
                (
                    "operation_run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="qc_results",
                        to="lims.operationrun",
                    ),
                ),
                (
                    "submission_record",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="qc_results",
                        to="lims.submissionrecord",
                    ),
                ),
                (
                    "task_run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="qc_results",
                        to="lims.taskrun",
                    ),
                ),
            ],
            options={
                "ordering": ["-reviewed_at", "-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="qcresult",
            constraint=models.UniqueConstraint(fields=("task_run",), name="uniq_lims_qc_result_task_run"),
        ),
        migrations.AddIndex(
            model_name="qcresult",
            index=models.Index(fields=["decision", "-reviewed_at"], name="lims_qc_result_decision_idx"),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0031_userprofile_projectmembershiprolehistory"),
    ]

    operations = [
        migrations.AddField(
            model_name="usernotification",
            name="attempts",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="usernotification",
            name="dead_lettered_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="usernotification",
            name="delivered_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="usernotification",
            name="delivery_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("sent", "Sent"),
                    ("failed", "Failed"),
                    ("dead_letter", "Dead Letter"),
                ],
                default="pending",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="usernotification",
            name="last_error",
            field=models.CharField(blank=True, default="", max_length=512),
        ),
        migrations.AddField(
            model_name="usernotification",
            name="max_attempts",
            field=models.PositiveIntegerField(default=3),
        ),
        migrations.AddField(
            model_name="usernotification",
            name="next_attempt_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="usernotification",
            name="provider",
            field=models.CharField(default="default", max_length=32),
        ),
        migrations.AlterField(
            model_name="usernotification",
            name="channel",
            field=models.CharField(
                choices=[
                    ("in_app", "In App"),
                    ("email", "Email"),
                    ("webhook", "Webhook"),
                ],
                max_length=16,
            ),
        ),
    ]

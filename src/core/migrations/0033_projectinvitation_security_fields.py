from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0032_usernotification_delivery_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="projectinvitation",
            name="max_token_attempts",
            field=models.PositiveIntegerField(default=5),
        ),
        migrations.AddField(
            model_name="projectinvitation",
            name="resent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="projectinvitation",
            name="revoked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="projectinvitation",
            name="token_attempts",
            field=models.PositiveIntegerField(default=0),
        ),
    ]

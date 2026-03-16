from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_privacyaction'),
    ]

    operations = [
        migrations.CreateModel(
            name='AgentRun',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('actor_id', models.CharField(blank=True, default='', max_length=200)),
                ('prompt', models.TextField(blank=True, default='')),
                ('allowed_tools', models.JSONField(blank=True, default=list)),
                ('timeout_seconds', models.IntegerField(default=60)),
                ('status', models.CharField(choices=[('queued', 'Queued'), ('running', 'Running'), ('completed', 'Completed'), ('failed', 'Failed'), ('cancelled', 'Cancelled'), ('timed_out', 'Timed Out')], default='queued', max_length=16)),
                ('output', models.JSONField(blank=True, default=dict)),
                ('error_message', models.CharField(blank=True, default='', max_length=512)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]

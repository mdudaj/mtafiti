from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0009_privacyprofile_consentevent'),
    ]

    operations = [
        migrations.CreateModel(
            name='ResidencyProfile',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
                ('allowed_regions', models.JSONField(blank=True, default=list)),
                ('blocked_regions', models.JSONField(blank=True, default=list)),
                ('enforcement_mode', models.CharField(choices=[('advisory', 'Advisory'), ('enforced', 'Enforced')], default='advisory', max_length=16)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('active', 'Active'), ('deprecated', 'Deprecated')], default='draft', max_length=16)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]

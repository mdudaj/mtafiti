from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0008_retentionrule_retentionhold_retentionrun'),
    ]

    operations = [
        migrations.CreateModel(
            name='PrivacyProfile',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
                (
                    'lawful_basis',
                    models.CharField(
                        choices=[
                            ('contract', 'Contract'),
                            ('legal_obligation', 'Legal Obligation'),
                            ('consent', 'Consent'),
                            ('legitimate_interest', 'Legitimate Interest'),
                        ],
                        max_length=32,
                    ),
                ),
                ('consent_required', models.BooleanField(default=False)),
                ('consent_state', models.CharField(default='unknown', max_length=16)),
                ('privacy_flags', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='ConsentEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    'consent_state',
                    models.CharField(
                        choices=[('unknown', 'Unknown'), ('granted', 'Granted'), ('withdrawn', 'Withdrawn'), ('expired', 'Expired')],
                        max_length=16,
                    ),
                ),
                ('reason', models.CharField(blank=True, default='', max_length=512)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'profile',
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='consent_events', to='core.privacyprofile'),
                ),
            ],
        ),
    ]

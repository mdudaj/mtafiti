from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0007_datacontract'),
    ]

    operations = [
        migrations.CreateModel(
            name='RetentionRule',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('scope', models.JSONField(blank=True, default=dict)),
                ('action', models.CharField(choices=[('archive', 'Archive'), ('delete', 'Delete')], max_length=16)),
                ('retention_period', models.CharField(max_length=32)),
                ('grace_period', models.CharField(blank=True, default='', max_length=32)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='RetentionHold',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('reason', models.CharField(blank=True, default='', max_length=512)),
                ('active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('released_at', models.DateTimeField(blank=True, null=True)),
                (
                    'asset',
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='retention_holds', to='core.dataasset'),
                ),
            ],
        ),
        migrations.CreateModel(
            name='RetentionRun',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('mode', models.CharField(choices=[('dry_run', 'Dry Run'), ('execute', 'Execute')], max_length=16)),
                ('status', models.CharField(choices=[('started', 'Started'), ('completed', 'Completed'), ('failed', 'Failed')], default='started', max_length=16)),
                ('summary', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                (
                    'rule',
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='runs', to='core.retentionrule'),
                ),
            ],
        ),
    ]

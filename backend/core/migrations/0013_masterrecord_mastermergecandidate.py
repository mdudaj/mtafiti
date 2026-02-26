from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0012_referencedataset_referencedatasetversion'),
    ]

    operations = [
        migrations.CreateModel(
            name='MasterMergeCandidate',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('entity_type', models.CharField(max_length=100)),
                ('target_master_id', models.UUIDField(db_index=True)),
                ('source_master_refs', models.JSONField(blank=True, default=list)),
                ('proposed_attributes', models.JSONField(blank=True, default=dict)),
                ('confidence', models.FloatField(blank=True, null=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', max_length=16)),
                ('approved_by', models.CharField(blank=True, default='', max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='MasterRecord',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('entity_type', models.CharField(max_length=100)),
                ('master_id', models.UUIDField(db_index=True, default=uuid.uuid4)),
                ('version', models.IntegerField(default=1)),
                ('attributes', models.JSONField(blank=True, default=dict)),
                ('survivorship_policy', models.JSONField(blank=True, default=dict)),
                ('confidence', models.FloatField(blank=True, null=True)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('active', 'Active'), ('superseded', 'Superseded'), ('archived', 'Archived')], default='draft', max_length=16)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('entity_type', 'master_id', 'version'), name='uniq_master_record_version')],
            },
        ),
    ]

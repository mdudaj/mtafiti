from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0011_accessrequest'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReferenceDataset',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
                ('owner', models.CharField(blank=True, default='', max_length=200)),
                ('domain', models.CharField(blank=True, default='', max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('name',), name='uniq_reference_dataset_name')],
            },
        ),
        migrations.CreateModel(
            name='ReferenceDatasetVersion',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('version', models.IntegerField()),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('approved', 'Approved'), ('active', 'Active'), ('deprecated', 'Deprecated')], default='draft', max_length=16)),
                ('values', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('dataset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='versions', to='core.referencedataset')),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('dataset', 'version'), name='uniq_reference_dataset_version')],
            },
        ),
    ]

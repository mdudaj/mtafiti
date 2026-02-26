from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0016_collaborationdocument_collaborationdocumentversion'),
    ]

    operations = [
        migrations.CreateModel(
            name='NotebookWorkspace',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
                ('owner', models.CharField(blank=True, default='', max_length=200)),
                ('image', models.CharField(blank=True, default='', max_length=256)),
                ('cpu_limit', models.CharField(blank=True, default='', max_length=32)),
                ('memory_limit', models.CharField(blank=True, default='', max_length=32)),
                ('storage_mounts', models.JSONField(blank=True, default=list)),
                ('status', models.CharField(default='active', max_length=16)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('name',), name='uniq_notebook_workspace_name')],
            },
        ),
        migrations.CreateModel(
            name='NotebookSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('user_id', models.CharField(blank=True, default='', max_length=200)),
                ('pod_name', models.CharField(blank=True, default='', max_length=200)),
                ('status', models.CharField(choices=[('started', 'Started'), ('terminated', 'Terminated'), ('resource_limited', 'Resource Limited')], default='started', max_length=32)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('ended_at', models.DateTimeField(blank=True, null=True)),
                ('workspace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sessions', to='core.notebookworkspace')),
            ],
        ),
        migrations.CreateModel(
            name='NotebookExecution',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('cell_ref', models.CharField(blank=True, default='', max_length=200)),
                ('status', models.CharField(choices=[('requested', 'Requested'), ('completed', 'Completed'), ('failed', 'Failed')], default='requested', max_length=16)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('requested_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='executions', to='core.notebooksession')),
            ],
        ),
    ]

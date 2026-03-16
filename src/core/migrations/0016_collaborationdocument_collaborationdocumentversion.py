from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0015_printjob'),
    ]

    operations = [
        migrations.CreateModel(
            name='CollaborationDocument',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=200)),
                ('object_key', models.CharField(max_length=512)),
                ('content_type', models.CharField(blank=True, default='', max_length=100)),
                ('owner', models.CharField(blank=True, default='', max_length=200)),
                ('status', models.CharField(default='active', max_length=16)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('object_key',), name='uniq_collaboration_object_key')],
            },
        ),
        migrations.CreateModel(
            name='CollaborationDocumentVersion',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('version', models.IntegerField()),
                ('object_key', models.CharField(max_length=512)),
                ('summary', models.CharField(blank=True, default='', max_length=512)),
                ('editor', models.CharField(blank=True, default='', max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='versions', to='core.collaborationdocument')),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('document', 'version'), name='uniq_collaboration_doc_version')],
            },
        ),
    ]

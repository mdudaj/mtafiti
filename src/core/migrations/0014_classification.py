from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0013_masterrecord_mastermergecandidate'),
    ]

    operations = [
        migrations.CreateModel(
            name='Classification',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
                ('level', models.CharField(choices=[('public', 'Public'), ('internal', 'Internal'), ('confidential', 'Confidential'), ('restricted', 'Restricted')], max_length=16)),
                ('description', models.CharField(blank=True, default='', max_length=512)),
                ('tags', models.JSONField(blank=True, default=list)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('active', 'Active'), ('deprecated', 'Deprecated')], default='draft', max_length=16)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('name',), name='uniq_classification_name')],
            },
        ),
    ]

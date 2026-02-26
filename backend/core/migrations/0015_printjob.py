from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0014_classification'),
    ]

    operations = [
        migrations.CreateModel(
            name='PrintJob',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('template_ref', models.CharField(max_length=256)),
                ('payload', models.JSONField(blank=True, default=dict)),
                ('output_format', models.CharField(choices=[('zpl', 'Zpl'), ('pdf', 'Pdf')], max_length=16)),
                ('destination', models.CharField(max_length=200)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('retrying', 'Retrying'), ('completed', 'Completed'), ('failed', 'Failed')], default='pending', max_length=16)),
                ('retry_count', models.IntegerField(default=0)),
                ('gateway_metadata', models.JSONField(blank=True, default=dict)),
                ('error_message', models.CharField(blank=True, default='', max_length=512)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]

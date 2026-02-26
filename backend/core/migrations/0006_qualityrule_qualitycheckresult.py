from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0005_dataasset_classifications_dataasset_description_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='QualityRule',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('rule_type', models.CharField(max_length=100)),
                ('params', models.JSONField(blank=True, default=dict)),
                ('severity', models.CharField(choices=[('warning', 'Warning'), ('error', 'Error')], default='warning', max_length=16)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'asset',
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='quality_rules', to='core.dataasset'),
                ),
            ],
        ),
        migrations.CreateModel(
            name='QualityCheckResult',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('status', models.CharField(choices=[('pass', 'Pass'), ('warn', 'Warn'), ('fail', 'Fail'), ('error', 'Error')], max_length=16)),
                ('details', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'rule',
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='results', to='core.qualityrule'),
                ),
            ],
        ),
    ]

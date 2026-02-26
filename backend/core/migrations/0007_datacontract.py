from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0006_qualityrule_qualitycheckresult'),
    ]

    operations = [
        migrations.CreateModel(
            name='DataContract',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('version', models.IntegerField()),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('active', 'Active'), ('deprecated', 'Deprecated')], default='draft', max_length=16)),
                ('schema', models.JSONField(blank=True, default=dict)),
                ('expectations', models.JSONField(blank=True, default=list)),
                ('owners', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'asset',
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contracts', to='core.dataasset'),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name='datacontract',
            constraint=models.UniqueConstraint(fields=('asset', 'version'), name='uniq_contract_asset_version'),
        ),
    ]

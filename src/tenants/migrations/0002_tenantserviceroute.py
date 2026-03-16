import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='TenantServiceRoute',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('service_key', models.CharField(max_length=64)),
                ('tenant_slug', models.CharField(max_length=64)),
                ('base_domain', models.CharField(max_length=253)),
                ('domain', models.CharField(max_length=253, unique=True)),
                ('workspace_path', models.CharField(blank=True, default='', max_length=128)),
                ('is_enabled', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='service_routes', to='tenants.tenant')),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('service_key', 'tenant_slug', 'base_domain'), name='uniq_tenant_service_route')],
            },
        ),
    ]

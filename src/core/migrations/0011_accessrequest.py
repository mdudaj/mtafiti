from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0010_residencyprofile'),
    ]

    operations = [
        migrations.CreateModel(
            name='AccessRequest',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('subject_ref', models.CharField(max_length=512)),
                ('requester', models.CharField(max_length=200)),
                ('access_type', models.CharField(choices=[('read', 'Read'), ('write', 'Write'), ('admin', 'Admin'), ('export', 'Export')], max_length=16)),
                ('justification', models.TextField(blank=True, default='')),
                ('status', models.CharField(choices=[('submitted', 'Submitted'), ('in_review', 'In Review'), ('approved', 'Approved'), ('denied', 'Denied'), ('expired', 'Expired'), ('revoked', 'Revoked')], default='submitted', max_length=16)),
                ('approver', models.CharField(blank=True, default='', max_length=200)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]

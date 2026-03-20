import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lims", "0014_formpackage_formpackagechoicelist_formpackageversion_and_more"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="workflowstepbinding",
            name="uniq_lims_wf_step_binding_scope",
        ),
        migrations.RemoveField(
            model_name="workflowstepbinding",
            name="field_keys",
        ),
        migrations.RemoveField(
            model_name="workflowstepbinding",
            name="schema_version",
        ),
        migrations.RemoveField(
            model_name="workflowstepbinding",
            name="ui_step",
        ),
        migrations.AddField(
            model_name="workflowstepbinding",
            name="form_package_version",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="workflow_step_bindings",
                to="lims.formpackageversion",
            ),
        ),
        migrations.AddField(
            model_name="workflowstepbinding",
            name="item_group_keys",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="workflowstepbinding",
            name="item_keys",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="workflowstepbinding",
            name="section_keys",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AlterField(
            model_name="workflowstepbinding",
            name="binding_type",
            field=models.CharField(
                choices=[
                    ("full_package", "Full Package"),
                    ("section_set", "Section Set"),
                    ("group_set", "Group Set"),
                    ("item_set", "Item Set"),
                ],
                default="full_package",
                max_length=32,
            ),
        ),
        migrations.AddConstraint(
            model_name="workflowstepbinding",
            constraint=models.UniqueConstraint(
                fields=("node", "form_package_version", "binding_type"),
                name="uniq_lims_wf_pkg_binding_scope",
            ),
        ),
    ]

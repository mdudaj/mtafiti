from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("lims", "0015_workflowstepbinding_form_package_bindings"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="workflowstepbinding",
            options={
                "ordering": [
                    "node__workflow_version__template__name",
                    "node__position",
                    "form_package_version__package__name",
                    "form_package_version__version_number",
                ],
            },
        ),
    ]

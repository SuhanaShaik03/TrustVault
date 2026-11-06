from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0002_auditevent_actor_reference_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditevent",
            name="ip_address",
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
    ]

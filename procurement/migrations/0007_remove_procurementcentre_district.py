# Generated migration to remove district field from ProcurementCentre
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("procurement", "0006_procurementcentre_slots_per_day_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="procurementcentre",
            name="district",
        ),
    ]

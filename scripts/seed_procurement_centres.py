import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'procurement_platform.settings')

import django
django.setup()

from procurement.models import ProcurementCentre, STATE_DISTRICT_CENTRE_MAP

created = 0
for state, districts in STATE_DISTRICT_CENTRE_MAP.items():
    for district, centre_names in districts.items():
        for centre_name in centre_names:
            code = (state[:3] + district[:3] + centre_name[:3]).replace(' ', '').upper()[:20]
            obj, was_created = ProcurementCentre.objects.get_or_create(
                code=code,
                defaults={
                    "name": centre_name,
                    "state": state,
                    "district": district,
                    "village": district,
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            print(f"{obj.state} | {obj.district} | {obj.name}")

print(f"\nSeed summary: {created} new centres added; {ProcurementCentre.objects.count()} total centres in database.")

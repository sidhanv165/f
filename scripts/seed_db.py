import os
import sys
from decimal import Decimal
from datetime import date, timedelta

# Ensure project root is on sys.path so Django settings module can be imported
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'procurement_platform.settings')
import django
django.setup()

from accounts.models import User, FarmerProfile
from procurement.models import ProcurementCentre, ProcurementRequest, STATE_DISTRICT_CENTRE_MAP

mocks = []
base_mobile = 9000000000
for i in range(1, 11):
    mobile = str(base_mobile + i)
    first = f"Farmer{i}"
    last = f"Demo"
    district = f"District{i%3 + 1}"
    village = f"Village{i%5 + 1}"
    # each farmer will have 1 or 2 bookings
    bookings = []
    if i % 2 == 0:
        bookings = [
            ("Tomato", Decimal("120.5"), date.today() + timedelta(days=7 + i)),
        ]
    else:
        bookings = [
            ("Wheat", Decimal("200"), date.today() + timedelta(days=3 + i)),
            ("Maize", Decimal("50"), date.today() + timedelta(days=10 + i)),
        ]

    mocks.append({
        "mobile": mobile,
        "first": first,
        "last": last,
        "district": district,
        "village": village,
        "bookings": bookings,
    })

created_centres = 0
for state, districts in STATE_DISTRICT_CENTRE_MAP.items():
    for district, centre_names in districts.items():
        for centre_name in centre_names:
            code = (state[:3] + district[:3] + centre_name[:3]).replace(' ', '').upper()[:20]
            obj, created = ProcurementCentre.objects.get_or_create(
                code=code,
                defaults={
                    "name": centre_name,
                    "state": state,
                    "district": district,
                    "village": district,
                    "is_active": True,
                },
            )
            if created:
                created_centres += 1

created_users = 0
created_profiles = 0
created_bookings = 0

for entry in mocks:
    mobile = entry["mobile"]
    user = None
    if User.objects.filter(mobile=mobile).exists():
        user = User.objects.get(mobile=mobile)
        print(f"User exists: {mobile} -> {user.full_name}")
    else:
        user = User.objects.create_user(mobile, "testpass123", first_name=entry["first"], last_name=entry["last"])
        # ensure role
        user.role = User.Role.FARMER
        user.save()
        created_users += 1
        print(f"Created user: {mobile} -> {user.full_name}")

    if not hasattr(user, 'farmer_profile') or user.farmer_profile is None:
        FarmerProfile.objects.create(user=user, district=entry["district"], village=entry["village"])
        created_profiles += 1
        print(f"  Created FarmerProfile for {mobile}")
    else:
        # update district/village if blank
        profile = user.farmer_profile
        profile.district = profile.district or entry["district"]
        profile.village = profile.village or entry["village"]
        profile.save()

    for crop, qty, pref_date in entry["bookings"]:
        # Avoid duplicates by checking an identical booking (same crop, qty, preferred_date)
        exists = ProcurementRequest.objects.filter(farmer=user, crop=crop, quantity=qty, preferred_date=pref_date).exists()
        if exists:
            print(f"  Booking exists for {mobile}: {crop} {qty} on {pref_date}")
            continue
        centre = ProcurementCentre.objects.order_by('name')[len(ProcurementRequest.objects.filter(farmer=user)) % ProcurementCentre.objects.count()]
        br = ProcurementRequest.objects.create(
            farmer=user,
            centre=centre,
            crop=crop,
            quantity=qty,
            preferred_date=pref_date,
            state="Maharashtra",
            district=entry["district"],
            village=entry["village"],
        )
        created_bookings += 1
        print(f"  Created booking {br.token_number} for {mobile}: {crop} {qty} on {pref_date} at {centre.name}")

print('\nSEED SUMMARY:')
print(f'  Centres created: {created_centres}')
print(f'  Users created: {created_users}')
print(f'  Profiles created: {created_profiles}')
print(f'  Bookings created: {created_bookings}')
print('\nSample bookings (first 10):')
for b in ProcurementRequest.objects.select_related('farmer', 'centre')[:10]:
    print(f'  {b.token_number} | {b.farmer.mobile} | {b.farmer.full_name} | {b.centre.name if b.centre else "-"} | {b.crop} | {b.quantity} | {b.preferred_date} | {b.status}')

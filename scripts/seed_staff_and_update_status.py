import os
import sys
from datetime import datetime

# Ensure project root on path
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'procurement_platform.settings')
import django
django.setup()

from accounts.models import User, StaffProfile
from procurement.models import ProcurementCentre, ProcurementRequest

# Create mock staff users
staff_specs = [
    {"mobile": "8000000001", "first": "StaffA", "last": "One", "designation": "Centre Clerk"},
    {"mobile": "8000000002", "first": "StaffB", "last": "Two", "designation": "Quality Lead"},
]

created_staff = 0
for s in staff_specs:
    mobile = s["mobile"]
    if User.objects.filter(mobile=mobile).exists():
        user = User.objects.get(mobile=mobile)
        print(f"Staff exists: {mobile} -> {user.full_name}")
    else:
        user = User.objects.create_user(mobile, "staffpass123", first_name=s["first"], last_name=s["last"])
        user.role = User.Role.STAFF
        user.save()
        created_staff += 1
        print(f"Created staff user: {mobile} -> {user.full_name}")

    if not hasattr(user, 'staff_profile') or user.staff_profile is None:
        first_state_id = ProcurementCentre.objects.filter(state__isnull=False).values_list("state_id", flat=True).first()
        StaffProfile.objects.create(user=user, designation=s["designation"], state_id=first_state_id)
        print(f"  Created StaffProfile for {mobile}")
    else:
        profile = user.staff_profile
        profile.designation = profile.designation or s["designation"]
        if profile.state_id is None:
            profile.state_id = ProcurementCentre.objects.filter(state__isnull=False).values_list("state_id", flat=True).first()
        profile.save()

# Ensure bookings have a centre assignment
centre_list = list(ProcurementCentre.objects.order_by('name'))
if not centre_list:
    print('No procurement centres available. Run seed_procurement_centres.py first.')
else:
    for booking in ProcurementRequest.objects.filter(centre__isnull=True):
        booking.centre = centre_list[booking.pk % len(centre_list)]
        update_fields = ['centre']
        if booking.district_id is None:
            booking.district = booking.centre.district
            update_fields.append('district')
        booking.save(update_fields=update_fields)

# Update four bookings to different statuses
statuses = [ProcurementRequest.Status.ALLOCATED, ProcurementRequest.Status.VERIFIED, ProcurementRequest.Status.COMPLETED, ProcurementRequest.Status.PENDING]
bookings = list(ProcurementRequest.objects.order_by('created_at')[:4])
updated = []
for booking, status in zip(bookings, statuses):
    old = booking.status
    booking.status = status
    booking.save(update_fields=['status'])
    updated.append((booking.token_number, old, booking.status))

print('\nSEED STAFF SUMMARY:')
print(f'  Staff users created: {created_staff}')
print('  Status updates:')
for tok, old, new in updated:
    print(f'    {tok}: {old} -> {new}')

print('\nCurrent top 8 bookings:')
for b in ProcurementRequest.objects.select_related('farmer', 'centre').order_by('-created_at')[:8]:
    print(f'  {b.token_number} | {b.farmer.mobile} | {b.centre.name if b.centre else "-"} | {b.crop} | {b.quantity} | {b.preferred_date} | {b.status}')

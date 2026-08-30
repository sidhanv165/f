import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User
from procurement.models import ProcurementCentre, ProcurementRequest, State


class Command(BaseCommand):
    help = "Seed demo farmers and bookings. Does not delete existing data."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=10, help="Number of farmers to create")
        parser.add_argument("--bookings-per-farmer", type=int, default=1, help="Number of bookings to create per farmer")
        parser.add_argument("--password", type=str, default="FarmerPass123", help="Password for created farmers")

    def handle(self, *args, **options):
        count = options["count"]
        bookings_per = options["bookings_per_farmer"]
        password = options["password"]

        created_users = []
        created_bookings = []

        # choose a centre to assign bookings; create a mock one if none exist
        centre = ProcurementCentre.objects.filter(is_active=True).first()
        if centre is None:
            state = State.objects.order_by("name").first()
            centre = ProcurementCentre.objects.create(
                code="MOCK-CTR-1",
                name="Mock Procurement Centre 1",
                state=state,
                agency="Mock Agency",
                is_active=True,
            )
            self.stdout.write(self.style.WARNING(f"No procurement centres found. Created mock centre: {centre.code}"))

        base_mobile = 9000000000
        for i in range(1, count + 1):
            mobile = str(base_mobile + i)
            # do not overwrite existing users
            user = User.objects.filter(mobile=mobile).first()
            if user:
                self.stdout.write(self.style.NOTICE(f"User with mobile {mobile} exists; skipping creation."))
            else:
                with transaction.atomic():
                    try:
                        user = User.objects.create_user(mobile, password)
                    except TypeError:
                        # fallback if signature is (mobile, password=None, **extra)
                        user = User.objects.create_user(mobile, password)
                    user.first_name = f"Farmer{i}"
                    user.role = User.Role.FARMER
                    user.is_active = True
                    user.save()
                    created_users.append(user)
                    self.stdout.write(self.style.SUCCESS(f"Created user {mobile} (Farmer{i})"))

            # create bookings for this user
            for b in range(bookings_per):
                preferred = date.today() + timedelta(days=(i + b) % 30 + 1)
                # avoid creating duplicate identical bookings for same user+date+centre
                exists = ProcurementRequest.objects.filter(farmer=user, preferred_date=preferred, centre=centre).exists()
                if exists:
                    self.stdout.write(self.style.NOTICE(f"Booking exists for {user.mobile} on {preferred}; skipping."))
                    continue
                booking = ProcurementRequest(
                    farmer=user,
                    centre=centre,
                    district=centre.district,
                    crop=random.choice(["Paddy", "Wheat", "Maize"]),
                    quantity=random.choice([100, 200, 250, 500]),
                    preferred_date=preferred,
                )
                booking.save()
                created_bookings.append(booking)
                self.stdout.write(self.style.SUCCESS(f"Created booking {booking.token_number} for {user.mobile} on {preferred}"))

        self.stdout.write(self.style.SUCCESS(f"Finished seeding: {len(created_users)} users, {len(created_bookings)} bookings created."))

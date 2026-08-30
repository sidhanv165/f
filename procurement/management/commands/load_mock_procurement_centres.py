from django.core.management.base import BaseCommand
from procurement.models import State, ProcurementCentre, District


class Command(BaseCommand):
    help = "Create lightweight mock procurement centres for testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--per-state",
            type=int,
            default=1,
            help="Number of mock centres to create per state (default: 1)",
        )

    def handle(self, *args, **options):
        per_state = int(options.get("per_state") or 1)
        created = 0
        updated = 0
        for state in State.objects.order_by("name"):
            districts = District.objects.filter(state=state).order_by("name")
            if not districts.exists():
                continue
            # choose up to per_state districts (round-robin)
            for i in range(per_state):
                district = districts[i % districts.count()]
                code = f"MOCK-{state.lgd_code}-{district.lgd_code}-{i+1:02d}"
                name = f"Mock Centre {i+1} - {district.name}"
                obj, created_flag = ProcurementCentre.objects.update_or_create(
                    code=code,
                    defaults={
                        "name": name,
                        "state": state,
                        "district": district,
                        "agency": "Mock Agency",
                        "is_active": True,
                    },
                )
                if created_flag:
                    created += 1
                else:
                    updated += 1
        self.stdout.write(self.style.SUCCESS(f"Mock centres created: {created} | updated: {updated}"))

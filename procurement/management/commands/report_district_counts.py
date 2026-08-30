from django.core.management.base import BaseCommand
from procurement.models import State, District


class Command(BaseCommand):
    help = "Report number of Districts per State"

    def handle(self, *args, **options):
        states = State.objects.order_by("name")
        total_states = 0
        total_districts = 0
        for s in states:
            count = District.objects.filter(state=s).count()
            self.stdout.write(f"{s.name} (lgd={s.lgd_code}): {count} districts")
            total_states += 1
            total_districts += count
        self.stdout.write(self.style.SUCCESS(f"Total states: {total_states} | Total districts: {total_districts}"))

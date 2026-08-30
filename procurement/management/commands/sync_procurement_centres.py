import json
from pathlib import Path

from django.core.management.base import BaseCommand

from procurement.models import District, ProcurementCentre, State


RESOURCE_DIR = Path(__file__).resolve().parents[3] / "procurement" / "resource"


def normalize_text(value):
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


class Command(BaseCommand):
    help = "Synchronize official procurement-centre data into the database."

    def handle(self, *args, **options):
        candidates = [
            RESOURCE_DIR / "normalized" / "procurement_centres.json",
            RESOURCE_DIR / "procurement_centres",
        ]
        files = []
        for candidate in candidates:
            if candidate.is_file():
                files.append(candidate)
            elif candidate.is_dir():
                files.extend(sorted(candidate.rglob("*.json")))

        if not files:
            self.stdout.write(self.style.WARNING("No procurement-centre resource files were found under %s" % RESOURCE_DIR))
            return

        created = 0
        updated = 0
        skipped = 0
        errors = 0

        for file_path in files:
            try:
                payload = json.loads(file_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                self.stdout.write(self.style.ERROR("Could not parse %s: %s" % (file_path, exc)))
                errors += 1
                continue

            records = payload if isinstance(payload, list) else payload.get("records", []) if isinstance(payload, dict) else []
            for record in records:
                if not isinstance(record, dict):
                    skipped += 1
                    continue

                code = normalize_text(record.get("centre_code") or record.get("code") or record.get("centreId") or record.get("id"))
                name = normalize_text(record.get("centre_name") or record.get("name") or record.get("procurement_centre"))
                if not name and not code:
                    skipped += 1
                    continue
                if not name:
                    name = code

                state_value = record.get("state") or record.get("state_name") or record.get("stateName") or record.get("state_lgd_name")
                district_value = record.get("district") or record.get("district_name") or record.get("districtName") or record.get("district_lgd_name")
                agency = normalize_text(record.get("agency") or record.get("department") or record.get("agency_name"))
                crop = normalize_text(record.get("crop") or record.get("commodity") or record.get("crop_name"))
                season = normalize_text(record.get("season") or record.get("season_name"))
                address = normalize_text(record.get("address") or record.get("location"))
                pincode = normalize_text(record.get("pincode") or record.get("pin_code"))

                state = self.resolve_state(state_value)
                if not state:
                    self.stdout.write(self.style.ERROR("Skipping centre %s because state could not be resolved: %s" % (name, state_value)))
                    errors += 1
                    continue

                district = self.resolve_district(state, district_value)

                if not code:
                    # centre code: use state prefix + name
                    code = f"{(state.name or '')[:3].upper()}-{name[:8].upper()}".replace(" ", "")

                centre, created_flag = ProcurementCentre.objects.update_or_create(
                    code=code,
                    defaults={
                        "name": name,
                        "state": state,
                        "district": district,
                        "agency": agency,
                        "crop": crop,
                        "season": season,
                        "address": address,
                        "pincode": pincode,
                        "is_active": True,
                    },
                )

                if created_flag:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(self.style.SUCCESS("Procurement centres imported. Created: %s | Updated: %s | Skipped: %s | Errors: %s" % (created, updated, skipped, errors)))

    def resolve_state(self, value):
        if value in (None, ""):
            return None
        key = normalize_text(value)
        if not key:
            return None
        match = State.objects.filter(name__iexact=key).first()
        if match:
            return match
        if str(key).isdigit():
            return State.objects.filter(lgd_code=int(key)).first()
        return None

    def resolve_district(self, state, value):
        if value in (None, ""):
            return None
        key = normalize_text(value)
        if not key:
            return None
        if str(key).isdigit():
            return District.objects.filter(state=state, lgd_code=int(key)).first()
        return District.objects.filter(state=state, name__iexact=key).first()

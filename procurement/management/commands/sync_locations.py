import csv
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from procurement.models import District, State, SubDistrict, Village


RESOURCE_DIR = Path(__file__).resolve().parents[3] / "procurement" / "resource" / "lgd"


def normalize_name(value):
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def find_first_value(row, *keys):
    for key in keys:
        if key in row and row.get(key) not in (None, ""):
            return row.get(key)
    # case-insensitive lookup
    normalized = {str(k).lower(): v for k, v in row.items()}
    for key in keys:
        lowered = key.lower()
        if lowered in normalized and normalized.get(lowered) not in (None, ""):
            return normalized.get(lowered)
    return ""


def detect_csv_encoding(path):
    """Try a small set of common encodings and return the first that can read a fragment without error."""
    encodings = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
    for enc in encodings:
        try:
            with path.open("r", encoding=enc) as fh:
                fh.read(4096)
            return enc
        except Exception:
            continue
    return "utf-8-sig"


class Command(BaseCommand):
    help = "Import LGD master location data into the Django database. Use --analyze to inspect CSV files before importing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--analyze",
            action="store_true",
            dest="analyze",
            help="Analyze LGD CSV files (print headers and sample values) without importing.",
        )
        parser.add_argument(
            "--sample-rows",
            type=int,
            dest="sample_rows",
            default=5,
            help="Number of sample rows to show when analyzing (default: 5)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            dest="dry_run",
            help="Do not write to the database. Show what would be created/updated.",
        )
        parser.add_argument(
            "--backup",
            action="store_true",
            dest="backup",
            help="Create a local backup of the SQLite DB file before making changes (recommended for production).",
        )
        parser.add_argument(
            "--include-sublevels",
            action="store_true",
            dest="include_sublevels",
            help="Also import subdistricts and villages if present. By default only states and districts are imported.",
        )

    def handle(self, *args, **options):
        analyze = options.get("analyze")
        sample_rows = options.get("sample_rows") or 5
        self.dry_run = bool(options.get("dry_run"))
        do_backup = bool(options.get("backup"))
        include_sublevels = bool(options.get("include_sublevels"))

        if not RESOURCE_DIR.exists():
            self.stdout.write(self.style.WARNING("No LGD resource directory found at %s" % RESOURCE_DIR))
            return

        files = {
            "states": sorted(RESOURCE_DIR.glob("*states*.csv")) + sorted(RESOURCE_DIR.glob("*state*.csv")),
            "districts": sorted(RESOURCE_DIR.glob("*district*.csv")),
            "subdistricts": sorted(RESOURCE_DIR.glob("*subdistrict*.csv")) + sorted(RESOURCE_DIR.glob("*taluk*.csv")),
            "villages": sorted(RESOURCE_DIR.glob("*village*.csv")),
        }

        # If analyze mode is requested, print file summaries and exit
        if analyze:
            self.stdout.write(self.style.MIGRATE_HEADING("LGD CSV Analyzer report"))
            for kind, paths in files.items():
                if not paths:
                    self.stdout.write(self.style.WARNING(f"No {kind} files found in {RESOURCE_DIR}"))
                    continue
                for p in paths:
                    self.stdout.write(self.style.MIGRATE_LABEL(f"\nFile: {p.name} ({kind})"))
                    try:
                        encoding = detect_csv_encoding(p)
                        with p.open("r", encoding=encoding, newline="") as fh:
                            reader = csv.DictReader(fh)
                            headers = reader.fieldnames or []
                            safe_headers = [h or "" for h in headers]
                            self.stdout.write("  Headers: %s" % ", ".join(safe_headers))

                            # read sample rows
                            samples = []
                            for i, row in enumerate(reader):
                                if i >= sample_rows:
                                    break
                                samples.append(row)

                            if not samples:
                                self.stdout.write("  (no sample rows)")
                            else:
                                for idx, row in enumerate(samples, start=1):
                                    # print a compact sample showing the most relevant columns
                                    displayed = []
                                    for col in safe_headers[:10]:
                                        val = row.get(col)
                                        displayed.append(f"{col}={repr(val)}")
                                    self.stdout.write(f"  Row {idx}: " + ", ".join(displayed))

                        # simple heuristic suggestions
                        suggestions = []
                        header_lc = [h.lower() for h in headers]
                        if kind == "states":
                            if any("lgd" in h for h in header_lc) or any("code" in h for h in header_lc):
                                suggestions.append("LGD/state code: look for headers with 'lgd', 'code', 'state_code'")
                            suggestions.append("State name: look for headers with 'state', 'state_name', 'name'")
                        if kind == "districts":
                            suggestions.append("District name: look for 'district', 'district_name', 'name'")
                            suggestions.append("State reference: look for 'state', 'state_code', 'state_lgd', 'state_id'")
                            suggestions.append("District LGD code: look for 'lgd', 'district_code', 'lgd_district_code'")
                        if kind == "subdistricts":
                            suggestions.append("Subdistrict/taluk name: 'subdistrict', 'taluk', 'name'")
                            suggestions.append("District reference: 'district', 'district_id', 'district_code', 'lgd_district_code'")
                        if kind == "villages":
                            suggestions.append("Village name: 'village', 'village_name', 'name'")
                            suggestions.append("Subdistrict reference: 'subdistrict', 'taluk', 'subdistrict_id', 'subdistrict_code'")
                            suggestions.append("Village LGD code: 'lgd_village_code', 'village_code', 'lgd_code'")

                        if suggestions:
                            self.stdout.write("  Suggested column matches:")
                            for s in suggestions:
                                self.stdout.write("   - %s" % s)

                    except Exception:
                        # Avoid printing problematic binary/unencodable characters from malformed CSVs
                        self.stdout.write(self.style.ERROR(f"Failed to read {p.name} (skipping)."))
            self.stdout.write(self.style.SUCCESS("Analysis complete."))
            return

        # normal import path
        stats = {"states": 0, "districts": 0, "subdistricts": 0, "villages": 0, "created": 0, "updated": 0, "skipped": 0, "errors": 0}

        # For production safety: backup the DB when requested and not a dry-run
        if do_backup and not self.dry_run:
            try:
                from django.conf import settings
                import shutil
                from datetime import datetime

                db_name = settings.DATABASES.get("default", {}).get("NAME")
                if db_name and (str(db_name).endswith(".sqlite3") or str(db_name).endswith(".db") or str(db_name).endswith('.sqlite')):
                    backup_path = Path(db_name).with_suffix(Path(db_name).suffix + f".{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.bak")
                    shutil.copy2(db_name, str(backup_path))
                    self.stdout.write(self.style.NOTICE(f"SQLite DB backed up to {backup_path}"))
                else:
                    self.stdout.write(self.style.WARNING("Backup requested but DB is not SQLite or path not found. Please backup manually for production Postgres DBs."))
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"Failed to create DB backup: {exc}"))
                return

        state_map = {}
        if files["states"]:
            for csv_path in files["states"]:
                self.import_states(csv_path, stats, state_map)
        else:
            self.stdout.write(self.style.WARNING("No states CSV file found in %s" % RESOURCE_DIR))

        if files["districts"]:
            for csv_path in files["districts"]:
                self.import_districts(csv_path, stats, state_map)
        else:
            self.stdout.write(self.style.WARNING("No districts CSV file found in %s" % RESOURCE_DIR))

        if include_sublevels and files["subdistricts"]:
            for csv_path in files["subdistricts"]:
                self.import_subdistricts(csv_path, stats)
        elif include_sublevels:
            self.stdout.write(self.style.WARNING("No subdistrict CSV file found in %s" % RESOURCE_DIR))
        else:
            self.stdout.write(self.style.NOTICE("Skipping subdistrict import. Pass --include-sublevels to import it."))

        if include_sublevels and files["villages"]:
            for csv_path in files["villages"]:
                self.import_villages(csv_path, stats)
        elif include_sublevels:
            self.stdout.write(self.style.WARNING("No villages CSV file found in %s" % RESOURCE_DIR))
        else:
            self.stdout.write(self.style.NOTICE("Skipping village import. Pass --include-sublevels to import it."))

        self.stdout.write(self.style.SUCCESS("Import complete."))
        self.stdout.write(
            "Created: %s | Updated: %s | Skipped: %s | Errors: %s" % (
                stats["created"],
                stats["updated"],
                stats["skipped"],
                stats["errors"],
            )
        )

    def import_states(self, csv_path, stats, state_map):
        encoding = detect_csv_encoding(csv_path)
        with csv_path.open("r", encoding=encoding, newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                self.stdout.write(self.style.WARNING("States file %s is empty" % csv_path))
                return

            self.stdout.write("Importing states from %s..." % csv_path.name)
            for row in reader:
                name = normalize_name(find_first_value(row, "state_name", "state", "name", "state_name_en", "state_name_english"))
                code = find_first_value(row, "lgd_state_code", "state_lgd_code", "state_code", "lgd_code", "code")
                if not name and not code:
                    stats["skipped"] += 1
                    continue
                if not name:
                    stats["errors"] += 1
                    continue
                if not code:
                    code = 0
                try:
                    lgd_code = int(str(code).replace("-", "").strip())
                except ValueError:
                    self.stdout.write(self.style.ERROR("Invalid LGD code for state %s: %s" % (name, code)))
                    stats["errors"] += 1
                    continue

                if getattr(self, 'dry_run', False):
                    existing = State.objects.filter(lgd_code=lgd_code).first() or State.objects.filter(name=name).first()
                    if existing:
                        self.stdout.write(self.style.NOTICE(f"[dry-run] Would update State '{name}' (lgd={lgd_code})"))
                        stats["updated"] += 1
                        state_map[lgd_code] = existing
                    else:
                        self.stdout.write(self.style.NOTICE(f"[dry-run] Would create State '{name}' (lgd={lgd_code})"))
                        stats["created"] += 1
                        state_map[lgd_code] = None
                else:
                    obj, created = State.objects.update_or_create(name=name, defaults={"lgd_code": lgd_code})
                    state_map[lgd_code] = obj
                    if created:
                        stats["created"] += 1
                    else:
                        stats["updated"] += 1
                stats["states"] += 1

    def import_districts(self, csv_path, stats, state_map):
        encoding = detect_csv_encoding(csv_path)
        with csv_path.open("r", encoding=encoding, newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                return

            for row in reader:
                district_name = normalize_name(find_first_value(row, "district_name", "district", "name", "district_name_en", "district_name_english", "district_name_local"))
                state_code = find_first_value(row, "state_lgd_code", "state_code", "state_id", "state_lgd", "lgd_state_code")
                lgd_code = find_first_value(row, "lgd_district_code", "district_lgd_code", "district_code", "lgd_code", "code")
                if not district_name:
                    continue
                if not state_code:
                    self.stdout.write(self.style.ERROR("District row missing state code: %s" % district_name))
                    stats["errors"] += 1
                    continue
                try:
                    state_key = int(str(state_code).replace("-", "").strip())
                    district_key = int(str(lgd_code).replace("-", "").strip()) if str(lgd_code).strip() else 0
                except ValueError:
                    stats["errors"] += 1
                    continue

                state = state_map.get(state_key) or State.objects.filter(lgd_code=state_key).first()
                if not state:
                    self.stdout.write(self.style.ERROR("District %s could not be resolved to a valid State for code %s" % (district_name, state_code)))
                    stats["errors"] += 1
                    continue

                computed_key = district_key or (state_key * 1000 + len(District.objects.filter(state=state)) + 1)
                if getattr(self, 'dry_run', False):
                    existing = District.objects.filter(lgd_code=district_key).first() or District.objects.filter(state=state, name=district_name).first()
                    if existing:
                        self.stdout.write(self.style.NOTICE(f"[dry-run] Would update District '{district_name}' in State '{state.name}' (lgd={existing.lgd_code})"))
                        stats["updated"] += 1
                    else:
                        self.stdout.write(self.style.NOTICE(f"[dry-run] Would create District '{district_name}' in State '{state.name}' (lgd={computed_key})"))
                        stats["created"] += 1
                else:
                    obj, created = District.objects.update_or_create(
                        lgd_code=computed_key,
                        defaults={"state": state, "name": district_name},
                    )
                    if created:
                        stats["created"] += 1
                    else:
                        stats["updated"] += 1
                stats["districts"] += 1

    def import_subdistricts(self, csv_path, stats):
        encoding = detect_csv_encoding(csv_path)
        with csv_path.open("r", encoding=encoding, newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                return

            for row in reader:
                name = normalize_name(find_first_value(row, "subdistrict_name", "sub_district_name", "taluk_name", "taluk", "name"))
                district_code = find_first_value(row, "district_lgd_code", "district_code", "district_id", "lgd_district_code")
                lgd_code = find_first_value(row, "lgd_subdistrict_code", "subdistrict_lgd_code", "subdistrict_code", "lgd_code", "code")
                if not name:
                    continue
                if not district_code:
                    stats["errors"] += 1
                    continue
                try:
                    district_key = int(str(district_code).replace("-", "").strip())
                    subdistrict_key = int(str(lgd_code).replace("-", "").strip()) if str(lgd_code).strip() else 0
                except ValueError:
                    stats["errors"] += 1
                    continue

                district = District.objects.filter(lgd_code=district_key).first()
                if not district:
                    stats["errors"] += 1
                    continue
                obj, created = SubDistrict.objects.update_or_create(
                    lgd_code=subdistrict_key or (district_key * 100 + len(SubDistrict.objects.filter(district=district)) + 1),
                    defaults={"district": district, "name": name},
                )
                if created:
                    stats["created"] += 1
                else:
                    stats["updated"] += 1
                stats["subdistricts"] += 1

    def import_villages(self, csv_path, stats):
        encoding = detect_csv_encoding(csv_path)
        with csv_path.open("r", encoding=encoding, newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                return

            for row in reader:
                name = normalize_name(find_first_value(row, "village_name", "village", "name", "locality_name"))
                subdistrict_code = find_first_value(row, "subdistrict_lgd_code", "sub_district_lgd_code", "taluk_lgd_code", "subdistrict_code", "subdistrict_id")
                lgd_code = find_first_value(row, "lgd_village_code", "village_lgd_code", "village_code", "lgd_code", "code")
                if not name:
                    continue
                if not subdistrict_code:
                    stats["errors"] += 1
                    continue
                try:
                    subdistrict_key = int(str(subdistrict_code).replace("-", "").strip())
                    village_key = int(str(lgd_code).replace("-", "").strip()) if str(lgd_code).strip() else 0
                except ValueError:
                    stats["errors"] += 1
                    continue

                subdistrict = SubDistrict.objects.filter(lgd_code=subdistrict_key).first()
                if not subdistrict:
                    stats["errors"] += 1
                    continue

                obj, created = Village.objects.update_or_create(
                    lgd_code=village_key or (subdistrict_key * 100 + len(Village.objects.filter(subdistrict=subdistrict)) + 1),
                    defaults={"subdistrict": subdistrict, "name": name},
                )
                if created:
                    stats["created"] += 1
                else:
                    stats["updated"] += 1
                stats["villages"] += 1

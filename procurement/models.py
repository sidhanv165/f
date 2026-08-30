from django.conf import settings
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone


class TimeStampedModel(models.Model):
    """Abstract base model that provides created_at and updated_at timestamps."""

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class State(TimeStampedModel):
    name = models.CharField(max_length=150, unique=True)
    lgd_code = models.PositiveIntegerField(unique=True, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["name"])]

    def __str__(self):
        return self.name


class District(TimeStampedModel):
    state = models.ForeignKey(State, on_delete=models.PROTECT, related_name="districts")
    name = models.CharField(max_length=150)
    lgd_code = models.PositiveIntegerField(unique=True, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["state__name", "name"]
        constraints = [models.UniqueConstraint(fields=["state", "name"], name="unique_district_name_per_state")]
        indexes = [models.Index(fields=["state", "name"]) ]

    def __str__(self):
        return f"{self.name}, {self.state.name}"


class SubDistrict(TimeStampedModel):
    district = models.ForeignKey(District, on_delete=models.PROTECT, related_name="subdistricts")
    name = models.CharField(max_length=200)
    lgd_code = models.PositiveIntegerField(unique=True, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["district__state__name", "district__name", "name"]
        constraints = [models.UniqueConstraint(fields=["district", "name"], name="unique_subdistrict_name_per_district")]
        indexes = [models.Index(fields=["district", "name"]) ]

    def __str__(self):
        return f"{self.name}, {self.district.name}"


class Village(TimeStampedModel):
    subdistrict = models.ForeignKey(SubDistrict, on_delete=models.PROTECT, related_name="villages")
    name = models.CharField(max_length=200)
    lgd_code = models.PositiveIntegerField(unique=True, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["subdistrict__district__state__name", "subdistrict__district__name", "subdistrict__name", "name"]
        constraints = [models.UniqueConstraint(fields=["subdistrict", "name"], name="unique_village_name_per_subdistrict")]
        indexes = [models.Index(fields=["subdistrict", "name"]) ]

    def __str__(self):
        return f"{self.name}, {self.subdistrict.name}"


class ProcurementCentre(TimeStampedModel):
    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    state = models.ForeignKey(State, on_delete=models.PROTECT, related_name="procurement_centres", null=True, blank=True)
    # district relationship removed intentionally: procurement centres are not guaranteed to be district-scoped.
    # If needed later, centres can be associated with a village (optional) or a state.
    village = models.ForeignKey(Village, on_delete=models.PROTECT, related_name="procurement_centres", null=True, blank=True)
    agency = models.CharField(max_length=150, blank=True, default="")
    crop = models.CharField(max_length=100, blank=True, default="")
    season = models.CharField(max_length=80, blank=True, default="")
    address = models.CharField(max_length=255, blank=True, default="")
    pincode = models.CharField(max_length=10, blank=True, default="")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    # Maximum number of slots (tickets) allowed per day for this centre. Null means unlimited.
    slots_per_day = models.PositiveIntegerField(null=True, blank=True, help_text="If set, maximum tickets per day for this centre. Null = unlimited")

    class Meta:
        ordering = ["state__name", "name"]
        indexes = [
            models.Index(fields=["state", "name"]),
            models.Index(fields=["code"]),
            models.Index(fields=["agency", "name"]),
        ]

    def __str__(self):
        state_part = self.state.name if self.state else "Unknown state"
        return f"{self.name} ({state_part})"


class ProcurementRequest(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ALLOCATED = "allocated", "Allocated"
        VERIFIED = "verified", "Verified"
        COMPLETED = "completed", "Completed"

    farmer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="procurement_requests",
    )
    village = models.ForeignKey(
        Village,
        on_delete=models.PROTECT,
        related_name="procurement_requests",
        null=True,
        blank=True,
    )
    centre = models.ForeignKey(
        "ProcurementCentre",
        on_delete=models.PROTECT,
        related_name="procurement_requests",
        null=True,
        blank=True,
    )
    crop = models.CharField(max_length=100)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    preferred_date = models.DateField()
    # Assigned ticket number for the preferred date (slot). Assigned at save time if possible.
    ticket_number = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "preferred_date"])]
        constraints = [
            models.UniqueConstraint(fields=["centre", "preferred_date", "ticket_number"], name="unique_centre_date_ticket"),
        ]

    @property
    def state(self):
        if self.village_id:
            return self.village.subdistrict.district.state
        if self.centre_id:
            return self.centre.state
        return None

    @property
    def district(self):
        # district can be derived from village; procurement centres are not district-scoped in this model.
        if self.village_id:
            return self.village.subdistrict.district
        # cannot reliably derive district from a centre that is only state-scoped
        return None

    @property
    def subdistrict(self):
        if self.village_id:
            return self.village.subdistrict
        return None

    @property
    def token_number(self):
        # If a slot (ticket) is assigned, present a slot-style token, else fall back to legacy FPR token
        if self.ticket_number and self.preferred_date and self.centre_id:
            # example: SLOT-KL-EKM-2026-08-30-001
            centre_code = getattr(self.centre, 'code', 'CENTRE')
            return f"SLOT-{centre_code}-{self.preferred_date.isoformat()}-{self.ticket_number:03d}"
        return f"FPR-{self.pk:04d}" if self.pk else "FPR-NEW"

    @property
    def scheduled_visit_date(self):
        return self.preferred_date

    @property
    def ticket_summary(self):
        centre_name = self.centre.name if self.centre else "Centre pending"
        return f"{self.token_number} • {self.scheduled_visit_date} • {centre_name}"

    def save(self, *args, **kwargs):
        """Assign a ticket_number automatically when saving if centre and preferred_date are set and no ticket exists.
        Uses a transaction and a small retry loop to avoid ticket collisions.
        """
        from django.db import IntegrityError

        if not self.ticket_number and self.centre_id and self.preferred_date:
            max_attempts = 5
            for attempt in range(max_attempts):
                try:
                    with transaction.atomic():
                        # collect occupied ticket numbers for this centre & date
                        occupied = list(
                            ProcurementRequest.objects.filter(
                                centre_id=self.centre_id, preferred_date=self.preferred_date
                            ).exclude(pk=self.pk).values_list("ticket_number", flat=True)
                        )
                        occupied_set = set([n for n in occupied if n])

                        slots_limit = getattr(self.centre, "slots_per_day", None)
                        if slots_limit:
                            # check if full
                            if len([n for n in occupied_set if n is not None]) >= slots_limit:
                                raise ValueError("No slots available for the selected date at this centre")
                            # find the smallest available ticket from 1..slots_limit
                            candidate = None
                            for i in range(1, slots_limit + 1):
                                if i not in occupied_set:
                                    candidate = i
                                    break
                            if candidate is None:
                                raise ValueError("No available ticket found")
                        else:
                            candidate = max(occupied_set) + 1 if occupied_set else 1

                        self.ticket_number = candidate
                        # attempt to save; unique constraint will prevent duplicates
                        super().save(*args, **kwargs)
                        return
                except IntegrityError:
                    # collision, retry
                    if attempt == max_attempts - 1:
                        raise
                    continue
        # default save path
        super().save(*args, **kwargs)

    def valid_centres(self):
        centres = ProcurementCentre.objects.filter(is_active=True)
        state_obj = self.state
        # Prefer centres that match the village's state and optionally match the village
        if self.village_id:
            centres = centres.filter(state=state_obj).filter(Q(village__isnull=True) | Q(village=self.village))
        elif state_obj:
            centres = centres.filter(state=state_obj)
        # If no state or village information is available, return all active centres
        return centres.order_by("name")

    def can_assign_centre(self, centre):
        if centre is None:
            return False
        if not centre.is_active:
            return False
        # If booking tied to a village, ensure centre is in the same state and if centre is village-scoped it matches
        if self.village_id:
            village_state = self.village.subdistrict.district.state
            if centre.state_id != village_state.id:
                return False
            if centre.village_id and centre.village_id != self.village_id:
                return False
            return True
        # If booking is only scoped to state/district, require centre's state to match
        state_obj = self.state
        if state_obj and centre.state_id != state_obj.id:
            return False
        return True

    def __str__(self):
        centre_name = self.centre.name if self.centre else "Unassigned centre"
        # Safely get farmer display name without assuming get_full_name exists
        farmer_name = None
        try:
            if hasattr(self.farmer, "get_full_name"):
                farmer_name = self.farmer.get_full_name()
        except Exception:
            farmer_name = None
        if not farmer_name:
            farmer_name = getattr(self.farmer, "mobile", None) or getattr(self.farmer, "username", str(self.farmer))
        return f"{self.token_number} - {farmer_name}: {self.crop} @ {centre_name}"

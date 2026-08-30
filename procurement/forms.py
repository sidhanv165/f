from django import forms
from django.db.models import Q

from .models import District, ProcurementCentre, ProcurementRequest, State, SubDistrict, Village


class ProcurementRequestForm(forms.ModelForm):
    crop = forms.CharField(label="Crop", max_length=100)
    quantity = forms.DecimalField(label="Quantity (kg)", min_value=0.01, max_digits=10, decimal_places=2)
    preferred_date = forms.DateField(label="Preferred date", widget=forms.DateInput(attrs={"type": "date"}))
    state = forms.ModelChoiceField(
        label="State / Union Territory",
        queryset=State.objects.none(),
        empty_label="Select state",
        required=True,
    )
    district = forms.ModelChoiceField(
        label="District",
        queryset=District.objects.none(),
        empty_label="Select district",
        required=True,
    )
    centre = forms.ModelChoiceField(
        label="Procurement Centre",
        queryset=ProcurementCentre.objects.none(),
        empty_label="Select a procurement centre",
        required=True,
    )

    class Meta:
        model = ProcurementRequest
        fields = ["crop", "quantity", "preferred_date", "state", "district", "centre"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["state"].queryset = State.objects.order_by("name")
        # If editing an existing request that has a village, derive initial state/district
        self._apply_initial_queryset_state()
        self._update_district_queryset()
        self._update_centre_queryset()

    def _coerce_pk(self, value):
        if value is None:
            return None
        if hasattr(value, "pk"):
            return value.pk
        return value

    def _apply_initial_queryset_state(self):
        # preserve behavior when an existing instance has a village set
        if self.instance and self.instance.pk and getattr(self.instance, "village", None):
            try:
                district = self.instance.village.subdistrict.district
                self.initial.setdefault("state", district.state)
                self.initial.setdefault("district", district)
            except Exception:
                pass

    def _selected_state_pk(self):
        value = self.data.get("state") or self.initial.get("state")
        return self._coerce_pk(value)

    def _selected_district_pk(self):
        value = self.data.get("district") or self.initial.get("district")
        return self._coerce_pk(value)

    def _update_district_queryset(self):
        state_id = self._selected_state_pk()
        if state_id:
            self.fields["district"].queryset = District.objects.filter(state_id=state_id).order_by("name")
        else:
            self.fields["district"].queryset = District.objects.none()

    def _update_centre_queryset(self):
        district_id = self._selected_district_pk()
        queryset = ProcurementCentre.objects.filter(is_active=True).select_related("state", "village").order_by("name")
        # If a district is selected, use its state to filter centres because centres are state-scoped
        if district_id:
            try:
                district_obj = District.objects.get(pk=district_id)
                queryset = queryset.filter(state_id=district_obj.state_id)
            except District.DoesNotExist:
                queryset = queryset.none()
        else:
            # fall back to selected state
            state_id = self._selected_state_pk()
            if state_id:
                queryset = queryset.filter(state_id=state_id)
        self.fields["centre"].queryset = queryset

    def clean(self):
        cleaned_data = super().clean()
        district = cleaned_data.get("district")
        centre = cleaned_data.get("centre")

        if district and centre:
            # centres are state-scoped in this deployment; ensure centre.state matches district.state
            if centre.state_id != district.state_id:
                self.add_error("centre", "The selected procurement centre is not in the chosen district's state.")

        # slot availability check: preferred_date is the slot date
        preferred_date = cleaned_data.get("preferred_date")
        if centre and preferred_date:
            slots_limit = getattr(centre, "slots_per_day", None)
            if slots_limit:
                existing_count = ProcurementRequest.objects.filter(centre=centre, preferred_date=preferred_date).exclude(pk=self.instance.pk if self.instance and self.instance.pk else None).count()
                if existing_count >= slots_limit:
                    self.add_error("preferred_date", "No slots available for the selected date at this centre.")

        return cleaned_data

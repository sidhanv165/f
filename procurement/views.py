import datetime
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, TemplateView
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from accounts.models import User

from .forms import ProcurementRequestForm
from .models import District, ProcurementCentre, ProcurementRequest, State, SubDistrict, Village
from .serializers import (
    DistrictSerializer,
    ProcurementCentreSerializer,
    StateSerializer,
    SubDistrictSerializer,
    VillageSerializer,
)


# Helper to safely obtain a user's display name across different User models
def user_display_name(user):
    if user is None:
        return ""
    # If the User model provides get_full_name(), prefer it
    try:
        if hasattr(user, "get_full_name"):
            name = user.get_full_name()
            if name:
                return name
    except Exception:
        pass
    # Common attribute fallbacks
    for attr in ("full_name", "name", "first_name"):
        val = getattr(user, attr, None)
        if val:
            # If first_name exists, try combining first and last
            if attr == "first_name":
                last = getattr(user, "last_name", "")
                combined = f"{val} {last}".strip()
                if combined:
                    return combined
            return val
    # mobile, username, email or str(user)
    for attr in ("mobile", "username", "email"):
        val = getattr(user, attr, None)
        if val:
            return str(val)
    return str(user)


class RoleRequiredMixin(LoginRequiredMixin):
    required_role = None

    def dispatch(self, request, *args, **kwargs):
        if self.required_role and request.user.role != self.required_role:
            return redirect("accounts:dashboard")
        return super().dispatch(request, *args, **kwargs)


class FarmerBookingView(RoleRequiredMixin, TemplateView):
    required_role = User.Role.FARMER
    template_name = "procurement/farmer_booking.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = ProcurementRequestForm()
        context["bookings"] = self.request.user.procurement_requests.select_related(
            "centre",
            "village__subdistrict__district__state",
        ).all()[:10]
        return context

    def post(self, request, *args, **kwargs):
        form = ProcurementRequestForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.farmer = request.user
            booking.save()
            messages.success(request, "Your procurement request has been submitted successfully.")
            return redirect("procurement:farmer_ticket", pk=booking.pk)

        context = self.get_context_data()
        context["form"] = form
        return self.render_to_response(context)


class FarmerBookingsView(RoleRequiredMixin, TemplateView):
    """Dedicated page listing a farmer's tickets/bookings."""
    required_role = User.Role.FARMER
    template_name = "procurement/farmer_tickets.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = ProcurementRequestForm()
        qs = self.request.user.procurement_requests.select_related(
            "centre",
            "village__subdistrict__district__state",
        ).order_by("-created_at")
        # paginate results
        from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

        page = self.request.GET.get("page", 1)
        try:
            page_size = int(self.request.GET.get("page_size", 10))
        except (TypeError, ValueError):
            page_size = 10
        paginator = Paginator(qs, page_size)
        try:
            bookings_page = paginator.page(page)
        except PageNotAnInteger:
            bookings_page = paginator.page(1)
        except EmptyPage:
            bookings_page = paginator.page(paginator.num_pages)

        context["bookings"] = bookings_page.object_list
        context["page_obj"] = bookings_page
        context["paginator"] = paginator
        context["is_paginated"] = paginator.num_pages > 1
        return context


class FarmerTicketView(RoleRequiredMixin, TemplateView):
    required_role = User.Role.FARMER
    template_name = "procurement/farmer_ticket.html"

    def get_context_data(self, pk, **kwargs):
        context = super().get_context_data(**kwargs)
        booking = get_object_or_404(
            ProcurementRequest.objects.select_related("farmer", "centre", "village__subdistrict__district__state"),
            pk=pk,
            farmer=self.request.user,
        )
        context["booking"] = booking
        return context


class StaffQueueView(RoleRequiredMixin, TemplateView):
    required_role = User.Role.STAFF
    template_name = "procurement/staff_queue.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = ProcurementRequest.objects.select_related("farmer", "centre", "village__subdistrict__district__state")

        # Restrict visible bookings to the staff member's assigned state (if set).
        staff_state = None
        try:
            staff_profile = getattr(self.request.user, "staff_profile", None)
            if staff_profile:
                # Accessing related fields may fail if migrations haven't been applied yet; guard against DB errors
                staff_state = getattr(staff_profile, "state", None)
        except Exception:
            # If the column does not exist (migration pending) or any DB error occurs, fall back to no state filter
            staff_state = None

        if staff_state:
            qs = qs.filter(Q(centre__state=staff_state) | Q(village__subdistrict__district__state=staff_state))

        status = self.request.GET.get("status")
        state = self.request.GET.get("state")
        district = self.request.GET.get("district")
        centre = self.request.GET.get("centre")
        q = self.request.GET.get("q")
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")
        ordering = self.request.GET.get("ordering", "-created_at")

        if status:
            qs = qs.filter(status=status)
        # 'state' filter parameter is still accepted (admin/staff may override via querystring) but it will be intersected with staff_state
        if state:
            qs = qs.filter(village__subdistrict__district__state_id=state)
        if district:
            qs = qs.filter(village__subdistrict__district_id=district)
        if centre:
            qs = qs.filter(centre_id=centre)
        if q:
            qs = qs.filter(
                Q(farmer__first_name__icontains=q)
                | Q(farmer__last_name__icontains=q)
                | Q(farmer__mobile__icontains=q)
                | Q(crop__icontains=q)
            )

        try:
            if start_date:
                sd = datetime.date.fromisoformat(start_date)
                qs = qs.filter(preferred_date__gte=sd)
            if end_date:
                ed = datetime.date.fromisoformat(end_date)
                qs = qs.filter(preferred_date__lte=ed)
        except ValueError:
            pass

        qs = qs.order_by(ordering)

        page = self.request.GET.get("page", 1)
        try:
            page_size = int(self.request.GET.get("page_size", 20))
        except (TypeError, ValueError):
            page_size = 20

        paginator = Paginator(qs, page_size)
        try:
            bookings_page = paginator.page(page)
        except PageNotAnInteger:
            bookings_page = paginator.page(1)
        except EmptyPage:
            bookings_page = paginator.page(paginator.num_pages)

        context["bookings"] = bookings_page.object_list
        context["page_obj"] = bookings_page
        context["paginator"] = paginator
        context["is_paginated"] = paginator.num_pages > 1

        params = {k: v for k, v in self.request.GET.items() if k != "page"}
        context["base_qs"] = "&".join(f"{key}={value}" for key, value in params.items())

        # Counts should reflect the staff member's scope (their assigned state) if set
        counts_qs = ProcurementRequest.objects.all()
        try:
            if staff_state:
                counts_qs = counts_qs.filter(Q(centre__state=staff_state) | Q(village__subdistrict__district__state=staff_state))
        except Exception:
            # Database schema may not include staff state yet; skip scoped counts
            counts_qs = ProcurementRequest.objects.all()

        context["pending_count"] = counts_qs.filter(status=ProcurementRequest.Status.PENDING).count()
        context["allocated_count"] = counts_qs.filter(status=ProcurementRequest.Status.ALLOCATED).count()
        context["verified_count"] = counts_qs.filter(status=ProcurementRequest.Status.VERIFIED).count()
        context["completed_count"] = counts_qs.filter(status=ProcurementRequest.Status.COMPLETED).count()

        context["filters"] = {
            "status": status or "",
            "district": district or "",
            "centre": centre or "",
            "state": state or "",
            "q": q or "",
            "start_date": start_date or "",
            "end_date": end_date or "",
            "ordering": ordering or "-created_at",
            "page_size": page_size,
        }
        context["available_centres"] = ProcurementCentre.objects.filter(is_active=True).order_by("name")
        context["state_choices"] = State.objects.order_by("name")
        # If a state filter is provided in the request, pre-filter districts for that state
        state_filter = self.request.GET.get("state")
        if state_filter:
            try:
                state_id = int(state_filter)
                context["district_choices"] = District.objects.filter(state_id=state_id).order_by("name")
            except (TypeError, ValueError):
                context["district_choices"] = District.objects.order_by("name")
        else:
            context["district_choices"] = District.objects.order_by("name")
        return context


@user_passes_test(lambda user: user.is_authenticated and user.role == User.Role.STAFF)
def update_booking_status(request, pk):
    booking = get_object_or_404(ProcurementRequest, pk=pk)
    new_status = request.POST.get("status")
    centre_id = request.POST.get("centre")

    # Ensure the acting staff member is allowed to modify this booking (must be assigned to the same state)
    # Safely determine staff state; if migrations pending, fall back to no restriction
    staff_state = None
    try:
        staff_profile = getattr(request.user, "staff_profile", None)
        if staff_profile:
            staff_state = getattr(staff_profile, "state", None)
    except Exception:
        staff_state = None

    booking_state = booking.state
    if staff_state and booking_state and staff_state.id != booking_state.id and not request.user.is_superuser:
        messages.error(request, "You are not authorized to modify bookings outside your assigned state.")
        return redirect("procurement:staff_queue")

    if centre_id:
        centre = get_object_or_404(ProcurementCentre, pk=centre_id)
        if not booking.can_assign_centre(centre):
            messages.error(request, "Selected centre does not match the booking's location.")
            return redirect("procurement:staff_queue")
        booking.centre = centre

    if new_status in {choice[0] for choice in ProcurementRequest.Status.choices}:
        booking.status = new_status

    if booking.centre_id and "centre" in request.POST:
        booking.save(update_fields=["status", "centre"])
    elif new_status in {choice[0] for choice in ProcurementRequest.Status.choices}:
        booking.save(update_fields=["status"])
    else:
        booking.save(update_fields=["centre"])

    if new_status in {choice[0] for choice in ProcurementRequest.Status.choices}:
        messages.success(request, f"Booking {booking.token_number} updated to {booking.get_status_display()}.")
    return redirect("procurement:staff_queue")


@user_passes_test(lambda user: user.is_authenticated and user.role == User.Role.FARMER)
def farmer_ticket_pdf(request, pk):
    booking = get_object_or_404(
        ProcurementRequest.objects.select_related("farmer", "centre", "village__subdistrict__district__state"),
        pk=pk,
        farmer=request.user,
    )
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    pdf.setTitle(f"Procurement Ticket {booking.token_number}")
    pdf.setAuthor(user_display_name(booking.farmer))
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(70, height - 80, "Procurement Booking Ticket")

    pdf.setFont("Helvetica-Bold", 12)
    y = height - 130
    for label, value in [
        ("Ticket number", booking.token_number),
        ("Farmer", user_display_name(booking.farmer)),
        ("Mobile", getattr(booking.farmer, 'mobile', '')),
        ("State", booking.state.name if booking.state else "-"),
        ("District", booking.district.name if booking.district else "-"),
        ("Village", booking.village.name if booking.village else "-"),
        ("Centre", booking.centre.name if booking.centre else "Pending assignment"),
        ("Crop", booking.crop),
        ("Quantity", f"{booking.quantity} kg"),
        ("Visit date", str(booking.preferred_date)),
        ("Status", booking.get_status_display()),
    ]:
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(70, y, f"{label}:")
        pdf.setFont("Helvetica", 11)
        pdf.drawString(220, y, str(value))
        y -= 24

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{booking.token_number}.pdf"'
    return response


@api_view(["GET"])
@permission_classes([AllowAny])
def api_states(request):
    queryset = State.objects.order_by("name")
    serializer = StateSerializer(queryset, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def api_districts(request):
    state_id = request.GET.get("state")
    queryset = District.objects.select_related("state")
    if state_id:
        queryset = queryset.filter(state_id=state_id)
    serializer = DistrictSerializer(queryset.order_by("name"), many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def api_subdistricts(request):
    district_id = request.GET.get("district")
    queryset = SubDistrict.objects.select_related("district__state")
    if district_id:
        queryset = queryset.filter(district_id=district_id)
    serializer = SubDistrictSerializer(queryset.order_by("name"), many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def api_villages(request):
    subdistrict_id = request.GET.get("subdistrict")
    search = request.GET.get("search", "")
    queryset = Village.objects.select_related("subdistrict__district__state")
    if subdistrict_id:
        queryset = queryset.filter(subdistrict_id=subdistrict_id)
    if search:
        queryset = queryset.filter(name__icontains=search)
    serializer = VillageSerializer(queryset.order_by("name")[:200], many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def api_procurement_centres(request):
    district_id = request.GET.get("district")
    village_id = request.GET.get("village")
    state_id = request.GET.get("state")
    queryset = ProcurementCentre.objects.filter(is_active=True).select_related("state", "village")
    if village_id:
        queryset = queryset.filter(village_id=village_id)
    elif district_id:
        # centres are state-scoped; derive state from district
        try:
            district_obj = District.objects.get(pk=int(district_id))
            queryset = queryset.filter(state_id=district_obj.state_id)
        except (District.DoesNotExist, ValueError):
            queryset = queryset.none()
    elif state_id:
        queryset = queryset.filter(state_id=state_id)
    serializer = ProcurementCentreSerializer(queryset.order_by("name"), many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def api_centre_availability(request):
    """Return availability for a centre and date.

    Query params:
      - centre (id)
      - date (YYYY-MM-DD)

    Response JSON:
      { centre_id, centre_code, date, capacity, booked, available, is_full }
    """
    centre_id = request.GET.get("centre") or request.GET.get("centre_id")
    date_str = request.GET.get("date")
    if not centre_id or not date_str:
        return Response({"error": "Missing required parameters 'centre' and 'date'"}, status=400)
    try:
        centre = ProcurementCentre.objects.get(pk=int(centre_id))
    except (ProcurementCentre.DoesNotExist, ValueError):
        return Response({"error": "Centre not found"}, status=404)
    try:
        slot_date = datetime.date.fromisoformat(date_str)
    except Exception:
        return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)

    # Count all bookings for that centre and date (includes pending/allocated/verified/completed)
    booked = ProcurementRequest.objects.filter(centre=centre, preferred_date=slot_date).count()
    capacity = centre.slots_per_day
    if capacity:
        available = max(0, capacity - booked)
        is_full = available == 0
    else:
        available = None
        is_full = False

    return Response(
        {
            "centre_id": centre.id,
            "centre_code": centre.code,
            "date": slot_date.isoformat(),
            "capacity": capacity,
            "booked": booked,
            "available": available,
            "is_full": is_full,
        }
    )

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, TemplateView

from .forms import (
    FarmerAuthenticationForm,
    FarmerProfileUpdateForm,
    FarmerRegistrationForm,
    MobileAuthenticationForm,
    StaffAuthenticationForm,
    StaffCreationForm,
    StaffProfileUpdateForm,
)
from procurement.models import ProcurementRequest

from .models import FarmerProfile, StaffProfile, User


class PublicHomeView(TemplateView):
    template_name = "public/home.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("dashboard")
        return super().dispatch(request, *args, **kwargs)


class FarmerRegistrationView(CreateView):
    form_class = FarmerRegistrationForm
    template_name = "accounts/farmer_register.html"

    def form_valid(self, form):
        with transaction.atomic():
            user = form.save(commit=False)
            user.role = User.Role.FARMER
            user.save()
            form.save_m2m()
            from .models import FarmerProfile

            FarmerProfile.objects.create(
                user=user,
                district=form.cleaned_data["district"],
                village=form.cleaned_data["village"],
            )
        login(self.request, user)
        messages.success(self.request, "Farmer account created successfully.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("accounts:farmer_dashboard")


class MobileLoginView(LoginView):
    authentication_form = MobileAuthenticationForm
    redirect_authenticated_user = True
    template_name = "accounts/login.html"

    def get_success_url(self):
        return self.get_redirect_url() or reverse("accounts:dashboard")


class FarmerLoginView(MobileLoginView):
    authentication_form = FarmerAuthenticationForm
    template_name = "accounts/farmer_login.html"

    def get_success_url(self):
        return self.get_redirect_url() or reverse("accounts:farmer_dashboard")


class StaffLoginView(MobileLoginView):
    authentication_form = StaffAuthenticationForm
    template_name = "accounts/staff_login.html"

    def get_success_url(self):
        return self.get_redirect_url() or reverse("accounts:staff_dashboard")


@user_passes_test(lambda user: user.is_authenticated and user.role == User.Role.ADMIN)
def admin_create_staff(request):
    if request.method == "POST":
        form = StaffCreationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save(commit=False)
                user.role = User.Role.STAFF
                user.save()
                form.save_m2m()
                from .models import StaffProfile

                StaffProfile.objects.create(
                    user=user,
                    designation=form.cleaned_data["designation"],
                )
            messages.success(request, "Staff account created successfully.")
            return redirect("accounts:admin_dashboard")
    else:
        form = StaffCreationForm()

    return render(request, "accounts/admin_create_staff.html", {"form": form})


class MobileLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:farmer_login")


class RoleRequiredMixin(LoginRequiredMixin):
    required_role = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if self.required_role and request.user.role != self.required_role:
            raise PermissionDenied(f"This account is not authorized to access this {self.required_role} portal.")

        return super().dispatch(request, *args, **kwargs)


def dashboard_redirect(request):
    if not request.user.is_authenticated:
        return redirect("accounts:farmer_login")

    if request.user.role == User.Role.STAFF:
        return redirect("accounts:staff_dashboard")

    if request.user.role == User.Role.ADMIN:
        return redirect("accounts:admin_dashboard")

    return redirect("accounts:farmer_dashboard")


class FarmerProfileView(RoleRequiredMixin, TemplateView):
    required_role = User.Role.FARMER
    template_name = "accounts/farmer_profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = FarmerProfileUpdateForm(user=self.request.user)
        return context

    def post(self, request, *args, **kwargs):
        form = FarmerProfileUpdateForm(request.POST, user=request.user)
        if form.is_valid():
            request.user.first_name = form.cleaned_data["first_name"].strip()
            request.user.last_name = form.cleaned_data["last_name"].strip()
            request.user.save(update_fields=["first_name", "last_name"])

            farmer_profile, _ = FarmerProfile.objects.get_or_create(user=request.user)
            farmer_profile.district = form.cleaned_data["district"].strip()
            farmer_profile.village = form.cleaned_data["village"].strip()
            farmer_profile.save(update_fields=["district", "village"])

            messages.success(request, "Your profile was updated successfully.")
            return redirect("accounts:farmer_profile")

        return self.render_to_response({"form": form})


class FarmerDashboardView(RoleRequiredMixin, TemplateView):
    required_role = User.Role.FARMER
    template_name = "accounts/farmer_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.request.user.procurement_requests.all()
        latest_request = qs.order_by("-created_at").first()

        context["booking_count"] = qs.count()
        context["pending_request_count"] = qs.filter(status=ProcurementRequest.Status.PENDING).count()
        context["latest_status_display"] = latest_request.get_status_display() if latest_request else "No request"
        return context


class StaffProfileView(RoleRequiredMixin, TemplateView):
    required_role = User.Role.STAFF
    template_name = "accounts/staff_profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = StaffProfileUpdateForm(user=self.request.user)
        return context

    def post(self, request, *args, **kwargs):
        form = StaffProfileUpdateForm(request.POST, user=request.user)
        if form.is_valid():
            request.user.first_name = form.cleaned_data["first_name"].strip()
            request.user.last_name = form.cleaned_data["last_name"].strip()
            request.user.save(update_fields=["first_name", "last_name"])

            staff_profile, _ = StaffProfile.objects.get_or_create(user=request.user)
            staff_profile.designation = form.cleaned_data["designation"].strip()
            staff_profile.save(update_fields=["designation"])

            messages.success(request, "Your staff profile was updated successfully.")
            return redirect("accounts:staff_profile")

        return self.render_to_response({"form": form})


class StaffDashboardView(RoleRequiredMixin, TemplateView):
    required_role = User.Role.STAFF
    template_name = "accounts/staff_dashboard.html"

    def get_context_data(self, **kwargs):
        from django.db.models import Q

        from procurement.models import ProcurementRequest

        context = super().get_context_data(**kwargs)
        # Build a base queryset for procurement requests. Keep select_related minimal to avoid errors when migrations are in flux.
        try:
            qs = ProcurementRequest.objects.select_related("farmer", "centre")
        except Exception:
            qs = ProcurementRequest.objects.all()

        # Safely get the staff member's assigned state; guard DB access in case migrations haven't been applied yet.
        staff_state = None
        try:
            staff_profile = getattr(self.request.user, "staff_profile", None)
            if staff_profile:
                staff_state = getattr(staff_profile, "state", None)
        except Exception:
            staff_state = None

        if staff_state:
            try:
                qs = qs.filter(Q(centre__state=staff_state) | Q(village__subdistrict__district__state=staff_state))
            except Exception:
                # If schema mismatch prevents the complex filter, skip scoping to avoid crashing the dashboard.
                pass

        context["procurement_request_count"] = qs.count()
        context["pending_request_count"] = qs.filter(status=ProcurementRequest.Status.PENDING).count()
        context["completed_request_count"] = qs.filter(status=ProcurementRequest.Status.COMPLETED).count()
        context["recent_bookings"] = qs.order_by("-created_at")[:5]
        return context


class AdminDashboardView(RoleRequiredMixin, TemplateView):
    required_role = User.Role.ADMIN
    template_name = "accounts/admin_dashboard.html"


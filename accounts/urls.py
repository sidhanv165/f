from django.urls import path

from .views import (
    AdminDashboardView,
    FarmerDashboardView,
    FarmerLoginView,
    FarmerProfileView,
    FarmerRegistrationView,
    MobileLoginView,
    MobileLogoutView,
    StaffDashboardView,
    StaffLoginView,
    StaffProfileView,
    admin_create_staff,
    dashboard_redirect,
)

app_name = "accounts"

urlpatterns = [
    # Farmer-facing auth
    path("register/", FarmerRegistrationView.as_view(), name="farmer_register"),
    path("login/farmer/", FarmerLoginView.as_view(), name="farmer_login"),

    # Staff auth (kept under /accounts/staff/login/ as requested)
    path("staff/login/", StaffLoginView.as_view(), name="staff_login"),

    # Common endpoints
    path("logout/", MobileLogoutView.as_view(), name="logout"),
    path("profile/farmer/", FarmerProfileView.as_view(), name="farmer_profile"),
    path("profile/staff/", StaffProfileView.as_view(), name="staff_profile"),

    # Dashboards
    path("dashboard/", dashboard_redirect, name="dashboard"),
    path("dashboard/farmer/", FarmerDashboardView.as_view(), name="farmer_dashboard"),
    path("dashboard/staff/", StaffDashboardView.as_view(), name="staff_dashboard"),
    path("dashboard/admin/", AdminDashboardView.as_view(), name="admin_dashboard"),

    # Admin utilities
    path("admin/staff/create/", admin_create_staff, name="admin_create_staff"),
]

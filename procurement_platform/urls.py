"""
URL configuration for procurement_platform project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from django.shortcuts import redirect

from accounts.views import PublicHomeView, dashboard_redirect
from accounts.models import User


def staff_root(request):
    """Redirect /staff/ to the staff dashboard if logged-in staff, otherwise to staff login."""
    if request.user.is_authenticated and getattr(request.user, "role", None) == User.Role.STAFF:
        return redirect("accounts:staff_dashboard")
    return redirect("accounts:staff_login")


urlpatterns = [
    path("", PublicHomeView.as_view(), name="home"),
    path("dashboard/", dashboard_redirect, name="dashboard"),
    # Permanent short alias for staff login at project root
    path("staff/login/", RedirectView.as_view(pattern_name="accounts:staff_login", permanent=True), name="staff_login_alias"),
    # Convenience root alias: /staff/ -> staff dashboard (if staff) else staff login
    path("staff/", staff_root, name="staff_root_alias"),
    path("accounts/", include("accounts.urls")),
    path("procurement/", include("procurement.urls")),
    path("admin/", admin.site.urls),
]

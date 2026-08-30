from django.urls import path

from .views import (
    FarmerBookingView,
    FarmerBookingsView,
    FarmerTicketView,
    StaffQueueView,
    api_districts,
    api_procurement_centres,
    api_states,
    api_subdistricts,
    api_villages,
    farmer_ticket_pdf,
    update_booking_status,
    api_centre_availability,
)

app_name = "procurement"

urlpatterns = [
    path("farmer/booking/", FarmerBookingView.as_view(), name="farmer_booking_create"),
    path("book/", FarmerBookingView.as_view(), name="farmer_booking"),
    path("farmer/bookings/", FarmerBookingsView.as_view(), name="farmer_booking_list"),
    path("my-bookings/", FarmerBookingsView.as_view(), name="farmer_bookings"),
    path("booking/<int:pk>/ticket/", FarmerTicketView.as_view(), name="farmer_ticket"),
    path("booking/<int:pk>/ticket/pdf/", farmer_ticket_pdf, name="farmer_ticket_pdf"),
    path("staff/queue/", StaffQueueView.as_view(), name="staff_queue"),
    path("queue/", StaffQueueView.as_view(), name="staff_queue_legacy"),
    path("booking/<int:pk>/status/", update_booking_status, name="update_booking_status"),
    path("api/locations/states/", api_states, name="api_states"),
    path("api/locations/districts/", api_districts, name="api_districts"),
    path("api/locations/subdistricts/", api_subdistricts, name="api_subdistricts"),
    path("api/locations/villages/", api_villages, name="api_villages"),
    path("api/procurement-centres/", api_procurement_centres, name="api_procurement_centres"),
    path("api/centres/availability/", api_centre_availability, name="api_centre_availability"),
]

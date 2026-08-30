from django.contrib import admin

from .models import District, ProcurementCentre, ProcurementRequest, State, SubDistrict, Village


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ("name", "lgd_code", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)
    ordering = ("name",)


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ("name", "state", "lgd_code", "is_active")
    search_fields = ("name", "state__name")
    list_filter = ("state", "is_active")
    ordering = ("state__name", "name")


@admin.register(SubDistrict)
class SubDistrictAdmin(admin.ModelAdmin):
    list_display = ("name", "district", "lgd_code", "is_active")
    search_fields = ("name", "district__name", "district__state__name")
    list_filter = ("district__state", "is_active")
    ordering = ("district__state__name", "district__name", "name")


@admin.register(Village)
class VillageAdmin(admin.ModelAdmin):
    list_display = ("name", "subdistrict", "lgd_code", "is_active")
    search_fields = ("name", "subdistrict__name", "subdistrict__district__name")
    list_filter = ("subdistrict__district__state", "is_active")
    ordering = ("subdistrict__district__state__name", "subdistrict__district__name", "subdistrict__name", "name")


@admin.register(ProcurementCentre)
class ProcurementCentreAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "state", "district", "agency", "slots_per_day", "is_active")
    search_fields = ("code", "name", "agency", "state__name", "district__name")
    list_filter = ("state", "district", "is_active", "agency")
    ordering = ("state__name", "district__name", "name")


@admin.register(ProcurementRequest)
class ProcurementRequestAdmin(admin.ModelAdmin):
    list_display = ("token_number", "farmer", "district", "centre", "preferred_date", "ticket_number", "crop", "status")
    search_fields = ("farmer__mobile", "crop", "centre__name", "district__name", "district__state__name")
    list_filter = ("status", "district__state", "district", "centre")
    ordering = ("-created_at",)

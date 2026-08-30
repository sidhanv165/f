from rest_framework import serializers

from .models import District, ProcurementCentre, State, SubDistrict, Village


class StateSerializer(serializers.ModelSerializer):
    class Meta:
        model = State
        fields = ["id", "name", "lgd_code"]


class DistrictSerializer(serializers.ModelSerializer):
    class Meta:
        model = District
        fields = ["id", "name", "lgd_code"]


class SubDistrictSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubDistrict
        fields = ["id", "name", "lgd_code"]


class VillageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Village
        fields = ["id", "name", "lgd_code"]


class ProcurementCentreSerializer(serializers.ModelSerializer):
    state_name = serializers.CharField(source="state.name", read_only=True)
    district_name = serializers.CharField(source="district.name", read_only=True, allow_null=True)

    class Meta:
        model = ProcurementCentre
        fields = [
            "id",
            "code",
            "name",
            "agency",
            "crop",
            "season",
            "state_name",
            "district_name",
        ]

from datetime import date

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from procurement.forms import ProcurementRequestForm
from procurement.models import District, ProcurementCentre, ProcurementRequest, State, SubDistrict, Village


class LocationAndProcurementTests(TestCase):
    def setUp(self):
        self.state = State.objects.create(name="Kerala", lgd_code=32)
        self.district = District.objects.create(state=self.state, name="Ernakulam", lgd_code=588)
        self.subdistrict = SubDistrict.objects.create(district=self.district, name="Kunnathunad", lgd_code=1200)
        self.village = Village.objects.create(subdistrict=self.subdistrict, name="Perumbavoor", lgd_code=20001)

        self.other_state = State.objects.create(name="Tamil Nadu", lgd_code=33)
        self.other_district = District.objects.create(state=self.other_state, name="Chennai", lgd_code=603)
        self.other_subdistrict = SubDistrict.objects.create(district=self.other_district, name="Adyar", lgd_code=1300)
        self.other_village = Village.objects.create(subdistrict=self.other_subdistrict, name="Adyar", lgd_code=21001)

        self.farmer = User.objects.create_user("9876543210", "StrongPass123")
        self.farmer.role = User.Role.FARMER
        self.farmer.save()

        self.centre = ProcurementCentre.objects.create(
            code="KL-EKM-001",
            name="Ernakulam Procurement Centre",
            state=self.state,
            village=self.village,
            agency="MARKFED",
            crop="Paddy",
            season="Kharif",
            is_active=True,
        )
        self.other_centre = ProcurementCentre.objects.create(
            code="TN-CHN-001",
            name="Chennai Procurement Centre",
            state=self.other_state,
            village=self.other_village,
            agency="Civil Supplies",
            crop="Paddy",
            season="Kharif",
            is_active=True,
        )

    def test_location_hierarchy_is_resolved_from_village(self):
        request = ProcurementRequest.objects.create(
            farmer=self.farmer,
            village=self.village,
            crop="Paddy",
            quantity="500.00",
            preferred_date=date(2026, 9, 15),
            centre=self.centre,
        )

        self.assertEqual(request.state, self.state)
        self.assertEqual(request.district, self.district)
        self.assertEqual(request.subdistrict, self.subdistrict)

    def test_valid_centres_are_limited_to_matching_district_and_village(self):
        request = ProcurementRequest.objects.create(
            farmer=self.farmer,
            village=self.village,
            crop="Paddy",
            quantity="500.00",
            preferred_date=date(2026, 9, 15),
        )

        self.assertIn(self.centre, request.valid_centres())
        self.assertNotIn(self.other_centre, request.valid_centres())
        self.assertTrue(request.can_assign_centre(self.centre))
        self.assertFalse(request.can_assign_centre(self.other_centre))

    def test_form_validates_selected_village_and_centre(self):
        form = ProcurementRequestForm(
            data={
                "crop": "Paddy",
                "quantity": "250.00",
                "preferred_date": "2026-09-15",
                "state": self.state.pk,
                "district": self.district.pk,
                "subdistrict": self.subdistrict.pk,
                "village": self.village.pk,
                "centre": self.centre.pk,
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_api_endpoints_return_location_data(self):
        response = self.client.get(reverse("procurement:api_states"))
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.json()), 0)

        district_response = self.client.get(reverse("procurement:api_districts"), {"state": self.state.pk})
        self.assertEqual(district_response.status_code, 200)
        self.assertEqual(len(district_response.json()), 1)

        centre_response = self.client.get(reverse("procurement:api_procurement_centres"), {"district": self.district.pk})
        self.assertEqual(centre_response.status_code, 200)
        self.assertEqual(len(centre_response.json()), 1)


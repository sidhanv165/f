from django.test import Client, TestCase
from django.urls import reverse

from .models import FarmerProfile, StaffProfile, User


class UserManagerTests(TestCase):
    def test_create_user_hashes_password(self):
        user = User.objects.create_user("9876543210", "StrongPass123")

        self.assertTrue(user.check_password("StrongPass123"))
        self.assertEqual(user.role, User.Role.FARMER)

    def test_create_user_stores_name_details(self):
        user = User.objects.create_user(
            "9876543211",
            "StrongPass123",
            first_name="Amit",
            last_name="Patel",
        )

        self.assertEqual(user.full_name, "Amit Patel")
        self.assertEqual(user.first_name, "Amit")
        self.assertEqual(user.last_name, "Patel")

    def test_create_superuser_sets_admin_metadata(self):
        admin = User.objects.create_superuser("9090909090", "AdminPass123")

        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertEqual(admin.role, User.Role.ADMIN)

    def test_profile_models_are_linked_to_users(self):
        farmer = User.objects.create_user("1111111111", "secret123", first_name="Ravi", last_name="Sharma")
        staff = User.objects.create_user("2222222222", "secret123", first_name="Neha", last_name="Verma", role=User.Role.STAFF)

        FarmerProfile.objects.create(user=farmer, district="Nashik", village="Dindori")
        StaffProfile.objects.create(user=staff, designation="Centre Manager")

        self.assertEqual(farmer.farmer_profile.district, "Nashik")
        self.assertEqual(staff.staff_profile.designation, "Centre Manager")


class DashboardRedirectTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_farmer_dashboard_redirect(self):
        farmer = User.objects.create_user("1111111111", "secret123")
        farmer.role = User.Role.FARMER
        farmer.save()

        self.client.force_login(farmer)
        response = self.client.get(reverse("accounts:dashboard"))

        self.assertRedirects(response, reverse("accounts:farmer_dashboard"))

    def test_staff_dashboard_redirect(self):
        staff = User.objects.create_user("2222222222", "secret123")
        staff.role = User.Role.STAFF
        staff.save()

        self.client.force_login(staff)
        response = self.client.get(reverse("accounts:dashboard"))

        self.assertRedirects(response, reverse("accounts:staff_dashboard"))

    def test_admin_dashboard_redirect(self):
        admin = User.objects.create_user("3333333333", "secret123")
        admin.role = User.Role.ADMIN
        admin.save()

        self.client.force_login(admin)
        response = self.client.get(reverse("accounts:dashboard"))

        self.assertRedirects(response, reverse("accounts:admin_dashboard"))

    def test_public_home_page_exists(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Farmer Procurement Platform")

    def test_public_farmer_registration_route_exists(self):
        response = self.client.get(reverse("accounts:farmer_register"))

        self.assertEqual(response.status_code, 200)

    def test_farmer_cannot_login_on_staff_portal(self):
        farmer = User.objects.create_user("1111111113", "secret123", first_name="Rohan")
        farmer.role = User.Role.FARMER
        farmer.save()

        response = self.client.post(
            reverse("accounts:staff_login"),
            {"username": farmer.mobile, "password": "secret123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Only procurement centre staff can sign in here.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_staff_cannot_login_on_farmer_portal(self):
        staff = User.objects.create_user("2222222224", "secret123", first_name="Kavya")
        staff.role = User.Role.STAFF
        staff.save()

        response = self.client.post(
            reverse("accounts:farmer_login"),
            {"username": staff.mobile, "password": "secret123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Only farmers can sign in here.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_farmer_profile_update_updates_name_and_details(self):
        farmer = User.objects.create_user("1111111112", "secret123", first_name="Ravi", last_name="Sharma")
        farmer.role = User.Role.FARMER
        farmer.save()
        FarmerProfile.objects.create(user=farmer, district="Nashik", village="Dindori")

        self.client.force_login(farmer)
        response = self.client.post(
            reverse("accounts:farmer_profile"),
            {
                "first_name": "Ravi",
                "last_name": "Patel",
                "district": "Pune",
                "village": "Khed",
            },
        )

        farmer.refresh_from_db()
        self.assertRedirects(response, reverse("accounts:farmer_profile"))
        self.assertEqual(farmer.first_name, "Ravi")
        self.assertEqual(farmer.last_name, "Patel")
        self.assertEqual(farmer.farmer_profile.district, "Pune")
        self.assertEqual(farmer.farmer_profile.village, "Khed")

    def test_staff_profile_update_updates_name_and_designation(self):
        staff = User.objects.create_user("2222222223", "secret123", first_name="Asha", last_name="Verma")
        staff.role = User.Role.STAFF
        staff.save()
        StaffProfile.objects.create(user=staff, designation="Quality Check")

        self.client.force_login(staff)
        response = self.client.post(
            reverse("accounts:staff_profile"),
            {
                "first_name": "Asha",
                "last_name": "Patil",
                "designation": "Centre Manager",
            },
        )

        staff.refresh_from_db()
        self.assertRedirects(response, reverse("accounts:staff_profile"))
        self.assertEqual(staff.first_name, "Asha")
        self.assertEqual(staff.last_name, "Patil")
        self.assertEqual(staff.staff_profile.designation, "Centre Manager")

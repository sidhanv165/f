from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm, UserCreationForm, UsernameField

from .models import User


class MobileAuthenticationForm(AuthenticationForm):
    username = UsernameField(
        label="Mobile number",
        widget=forms.TextInput(
            attrs={
                "autofocus": True,
                "autocomplete": "tel",
                "placeholder": "9876543210",
            }
        ),
    )


class RoleAuthenticationForm(MobileAuthenticationForm):
    allowed_role = None
    access_message = "This account cannot access this portal."

    def confirm_login_allowed(self, user):
        if self.allowed_role is not None and getattr(user, "role", None) != self.allowed_role:
            raise forms.ValidationError(
                self.access_message,
                code="invalid_role",
            )
        super().confirm_login_allowed(user)


class FarmerAuthenticationForm(RoleAuthenticationForm):
    allowed_role = User.Role.FARMER
    access_message = "Only farmers can sign in here."


class StaffAuthenticationForm(RoleAuthenticationForm):
    allowed_role = User.Role.STAFF
    access_message = "Only procurement centre staff can sign in here."


class FarmerRegistrationForm(UserCreationForm):
    mobile = forms.CharField(
        label="Mobile number",
        max_length=15,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "tel",
                "placeholder": "9876543210",
            }
        ),
    )
    first_name = forms.CharField(label="First name", max_length=50)
    last_name = forms.CharField(label="Last name", max_length=50)
    district = forms.CharField(label="District", max_length=100)
    village = forms.CharField(label="Village", max_length=100)

    class Meta:
        model = User
        fields = ("mobile", "first_name", "last_name", "password1", "password2", "district", "village")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.FARMER
        if commit:
            user.save()
            from .models import FarmerProfile

            FarmerProfile.objects.create(
                user=user,
                district=self.cleaned_data["district"],
                village=self.cleaned_data["village"],
            )
        return user


class FarmerProfileUpdateForm(forms.Form):
    first_name = forms.CharField(label="First name", max_length=50)
    last_name = forms.CharField(label="Last name", max_length=50, required=False)
    district = forms.CharField(label="District", max_length=100, required=False)
    village = forms.CharField(label="Village", max_length=100, required=False)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is None:
            return

        self.fields["first_name"].initial = user.first_name
        self.fields["last_name"].initial = user.last_name

        profile = getattr(user, "farmer_profile", None)
        if profile:
            self.fields["district"].initial = profile.district
            self.fields["village"].initial = profile.village


class StaffProfileUpdateForm(forms.Form):
    first_name = forms.CharField(label="First name", max_length=50)
    last_name = forms.CharField(label="Last name", max_length=50, required=False)
    designation = forms.CharField(label="Designation", max_length=100, required=False)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is None:
            return

        self.fields["first_name"].initial = user.first_name
        self.fields["last_name"].initial = user.last_name

        profile = getattr(user, "staff_profile", None)
        if profile:
            self.fields["designation"].initial = profile.designation


class StaffCreationForm(UserCreationForm):
    mobile = forms.CharField(
        label="Mobile number",
        max_length=15,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "tel",
                "placeholder": "9876543210",
            }
        ),
    )
    first_name = forms.CharField(label="First name", max_length=50)
    last_name = forms.CharField(label="Last name", max_length=50)
    designation = forms.CharField(label="Designation", max_length=100)

    class Meta:
        model = User
        fields = ("mobile", "first_name", "last_name", "designation", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.STAFF
        if commit:
            user.save()
            from .models import StaffProfile

            StaffProfile.objects.create(
                user=user,
                designation=self.cleaned_data["designation"],
            )
        return user


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("mobile", "first_name", "last_name", "role")


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = (
            "mobile",
            "first_name",
            "last_name",
            "role",
            "is_active",
            "is_staff",
            "is_superuser",
            "groups",
            "user_permissions",
        )

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, mobile, password=None, **extra_fields):
        if not mobile:
            raise ValueError("The mobile number is required.")

        user = self.model(mobile=mobile, **extra_fields)

        if password is not None:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, mobile, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(mobile, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        FARMER = "farmer", "Farmer"
        STAFF = "staff", "Procurement Centre Staff"
        ADMIN = "admin", "Administrator"

    mobile = models.CharField(max_length=15, unique=True)
    first_name = models.CharField(max_length=50, blank=True, default="")
    last_name = models.CharField(max_length=50, blank=True, default="")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.FARMER)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "mobile"
    REQUIRED_FIELDS = []

    @property
    def full_name(self):
        names = [self.first_name, self.last_name]
        return " ".join(part for part in names if part).strip() or self.mobile

    def __str__(self):
        return self.full_name


class FarmerProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="farmer_profile",
    )
    district = models.CharField(max_length=100, blank=True, default="")
    village = models.CharField(max_length=100, blank=True, default="")

    def __str__(self):
        return f"{self.user.full_name} ({self.user.mobile})"


class StaffProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="staff_profile",
    )
    designation = models.CharField(max_length=100, blank=True, default="")
    # Each staff member is associated with a State; staff should only manage bookings within their state.
    state = models.ForeignKey(
        "procurement.State",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="staff_profiles",
    )

    def __str__(self):
        state_name = self.state.name if self.state else "Unassigned"
        return f"{self.user.full_name} ({self.user.mobile}) - {state_name}"

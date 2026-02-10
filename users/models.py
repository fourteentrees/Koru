from django.db import models
from django.forms import ValidationError
from snowflakekit import SnowflakeGenerator, SnowflakeConfig
from koru.utils import ResourceModel, snowflaker
from moderation.models import UserViolation, UserRecord

FLAG_OPTS = [
    # Allow user to join staff-only spaces and put a staff badge on their profile. Permissions need to be handled separately.
    # Note that this flag is automatically set to true on people with is_staff=true!
    "staff",
    # This does nothing but show a special badge on the user profile.
    "donor",
    # Optable flag that adds a useless checkmark to the user profile.
    "useless_tick",
    # Will permadelete messages immediately instead of just marking them as deleted and then purging them after 30 days.
    "permadelete",
]

def validate_flags(value):
    """Validate that all flags are in the predefined list"""
    if not isinstance(value, list):
        raise ValidationError("Flags must be a list")
    for flag in value:
        if flag not in FLAG_OPTS:
            raise ValidationError(f"Invalid flag: {flag}")

# Create your models here.
from django.contrib.auth.models import (
    BaseUserManager, AbstractBaseUser, PermissionsMixin
)

class UserManager(BaseUserManager):
    def create_user(self, email, password=None):
        if not email:
            raise ValueError("Users must have an email address.")

        user = self.model(email=self.normalize_email(email))
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password):
        user = self.create_user(email,password=password)
        user.is_superuser = True
        user.is_staff = True
        user.save(using=self._db)

        return user

    def create_dependent_models(self, user):
        UserRecord.objects.create(user=user)
        UserSettings.objects.create(user=user)
        UserProfile.objects.create(user=user)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.CharField(max_length=64, primary_key=True, default=snowflaker, editable=False, unique=True)
    email = models.EmailField(
        verbose_name='email address',
        unique=True,
        db_index=True,
    )
    full_name = models.CharField(
        max_length=191,
        blank=True,
    )
    short_name = models.CharField(
        max_length=191,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    flags = models.JSONField(default=dict, validators=[validate_flags])
    # Account disabled by moderation
    suspended = models.BooleanField(default=False)
    suspended_since = models.DateTimeField(blank=True, null=True)
    moderation_appeal_denied = models.BooleanField(default=False)
    # Account disabled by user request
    disabled = models.BooleanField(default=False)
    # soft delete
    deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)

    username = models.CharField(max_length=32, unique=True)
    display_name = models.CharField(max_length=32, blank=True)

    moderation_record = models.OneToOneField(UserRecord, on_delete=models.CASCADE, related_name="user", null=True)
    settings = models.OneToOneField("UserSettings", on_delete=models.CASCADE, related_name="user", null=True)
    profile = models.OneToOneField("UserProfile", on_delete=models.CASCADE, related_name="user", null=True)

    # Whether this is the account where system DMs come from
    # DO NOT TOGGLE THIS. It will forbid you from joining servers and receiving DMs.
    system_account = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.short_name

    def __str__(self):
        return f"{self.email} ({self.full_name})"

class UserProfile(ResourceModel):
    id = models.CharField(max_length=64, primary_key=True, default=snowflaker, editable=False, unique=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    # This is where we'll put all the user-specific stuff that we want to be able to query on, like flags, etc.
    bio = models.TextField(blank=True, max_length=300, null=True)
    # default avatars coming soon!
    avatar = models.URLField(blank=True, null=True)
    bannerType = models.IntegerField(default=0, max=2)
    bannerColorHex = models.CharField(max_length=6, blank=True, null=True)
    bannerImage = models.URLField(blank=True, null=True)

    suspended = None
    deleted = None

class UserSettings(ResourceModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="settings")
    # This is where we'll put all the user-specific settings that we want to be able to query on, like flags, etc.
    theme = models.CharField(max_length=20, default="light")

    suspended = None
    deleted = None
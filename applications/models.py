from django.db import models
from koru.utils import ResourceModel, snowflake_from_timestamp
from django.forms import ValidationError

class BaseModel(ResourceModel):
    name = models.CharField(max_length=64)
    description = models.TextField(blank=True)
    owner_type = models.IntegerField(choices=[(0, "User"), (1, "Developer Team")])
    owner_user = models.ForeignKey("allauth.account.models.User", null=True, blank=True, on_delete=models.CASCADE)
    owner_dev_team = models.ForeignKey("DevTeam", null=True, blank=True, on_delete=models.CASCADE)

    class Meta:
        abstract = True

def validate_owner(value):
    if value not in [0, 1]:
        raise ValidationError("Owner type must be 0 (User) or 1 (Developer Team).")
    if value == 0 and not self.owner_user:
        raise ValidationError("User owner type must have an owner_user.")
    if value == 1 and not self.owner_dev_team:
        raise ValidationError("Developer Team owner type must have an owner_dev_team.")

class Application(BaseModel):
    # Receives snowflake, suspended, deleted from ResourceModel
    # Receives name, description, owner_type, owner_user, owner_dev_team from BaseModel
    features = models.JSONField(default=dict)
    installed_in_spaces = models.ManyToManyField("core.Space", related_name="installed_applications")
    installed_for_users = models.ManyToManyField("allauth.account.models.User", related_name="installed_applications")
    client_id = models.CharField(max_length=64, unique=True)
    client_secret = models.CharField(max_length=128)
    redirect_uris = models.JSONField(default=list)

class DevTeam(BaseModel):
    # Receives snowflake, suspended, deleted from ResourceModel
    # Receives name, description, owner_type, owner_user, owner_dev_team from BaseModel
    members = models.ManyToManyField("allauth.account.models.User", related_name="dev_teams")
    member_roles = models.JSONField(default=dict)  # e.g. {"user_id": "admin"}
    applications = models.ManyToManyField(Application, related_name="dev_teams")

class Bot(BaseModel):
    # Receives snowflake, suspended, deleted from ResourceModel
    # Receives name, description, owner_type, owner_user, owner_dev_team from BaseModel
    features = models.JSONField(default=dict)
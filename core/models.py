from django.db import models
from koru.utils import ResourceModel, snowflaker
from users.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Max
from django.core.validators import MinValueValidator

FEATURE_OPTS = [
    "staff_only",
    "vanity_url",
    "space_registry_submittable",
]

FEATURE_OPT_DESCS = {
    "staff_only": "Only users with the staff flag can join this space. Will feign nonexistence to users without the flag.",
    "vanity_url": "Allows the space to have a custom invite URL regardless of verification status. Vanity URL must be set separately and be unique across the platform.",
    "space_registry_submittable": "Allows the space to be submitted to the Space Registry regardless of member count or verification/official status.",
}

def validate_features(value):
    """Validate that all flags are in the predefined list"""
    if not isinstance(value, list):
        raise ValidationError("Flags must be a list")
    for flag in value:
        if flag not in FEATURE_OPTS:
            raise ValidationError(f"Invalid flag: {flag}")

class Space(ResourceModel):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, max_length=340)
    icon = models.URLField(blank=True, null=True)
    owner = models.ForeignKey("users.User", on_delete=models.CASCADE)

    members = models.ManyToManyField("users.User", related_name="spaces")
    member_count = models.IntegerField(default=0)
    features = models.JSONField(default=dict)
    # Prolific servers and official servers for popular things (except for the Koru instance) can be verified, which grants them:
    # 1. Vanity URL
    # 2. Ability to submit space to the Space Registry regardless of member count
    # 3. A special badge next to the server name everywhere
    server_verified = models.BooleanField(default=False)
    # For servers maintained by the instance admin team. Same as verified just with a different coat of paint
    server_official = models.BooleanField(default=False)
    server_tags = models.JSONField(default=list, blank=True)
    vanity_url = models.CharField(max_length=64, blank=True, null=True, unique=True)
    space_registry_listed = models.BooleanField(default=False)
    space_reg_entry = models.OneToOneField("SpaceRegEntry", on_delete=models.SET_NULL, null=True, blank=True, related_name="space")

class SpaceRegEntry(ResourceModel):
    space = models.OneToOneField(Space, on_delete=models.CASCADE, related_name="registry_entry")
    description = models.TextField(blank=True, max_length=340)
    tags = models.JSONField(default=list, blank=True)

class SpaceSettingsIndex(ResourceModel):
    space = models.OneToOneField(Space, on_delete=models.CASCADE, related_name="settings")

class SpaceRole(ResourceModel):
    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name="roles")
    name = models.CharField(max_length=64)
    hex = models.CharField(max_length=6, default="000000")
    icon = models.URLField(blank=True, null=True)
    mentionable_by_everyone = models.BooleanField(default=False)
    hoist = models.BooleanField(default=False)
    default_role = models.BooleanField(default=False)
    permissions = models.JSONField(default=dict)

    # 1 == lowest, N == highest; higher number == higher in hierarchy
    position = models.IntegerField(validators=[MinValueValidator(1)], db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["space", "position"], name="unique_role_position_per_space")
        ]
        ordering = ["-position", "name"]

    def clean(self):
        # ensure position is integer >= 1
        if self.position is not None and self.position < 1:
            raise ValidationError("Position must be >= 1")

    def save(self, *args, **kwargs):
        # Normalize space existence
        if self.space_id is None:
            raise ValidationError("Space must be set for a role")

        # Count existing roles in the space (excluding self when updating)
        existing_qs = SpaceRole.objects.filter(space=self.space)
        if self.pk:
            existing_qs = existing_qs.exclude(pk=self.pk)
        count = existing_qs.count()

        # If creating and no position provided, append to end
        if not self.pk and (self.position is None):
            self.position = count + 1
            super().save(*args, **kwargs)
            return

        # For creation allowed positions: 1..count+1
        # For update allowed positions: 1..count+1 (count excludes self, so max is current total)
        max_allowed = count + 1
        if self.position is None or not (1 <= self.position <= max_allowed):
            raise ValidationError(f"Position must be between 1 and {max_allowed}")

        with transaction.atomic():
            if not self.pk:
                # Inserting: shift existing roles at or after position up by 1
                SpaceRole.objects.filter(space=self.space, position__gte=self.position).update(position=F("position") + 1)
                super().save(*args, **kwargs)
            else:
                # Updating: move existing role from old_pos to new_pos and shift others
                old = SpaceRole.objects.select_for_update().get(pk=self.pk).position
                new = self.position
                if new == old:
                    super().save(*args, **kwargs)
                    return

                if new < old:
                    # shift roles in [new, old-1] up by 1
                    SpaceRole.objects.filter(
                        space=self.space,
                        position__gte=new,
                        position__lt=old
                    ).exclude(pk=self.pk).update(position=F("position") + 1)
                else:
                    # new > old: shift roles in [old+1, new] down by 1
                    SpaceRole.objects.filter(
                        space=self.space,
                        position__gt=old,
                        position__lte=new
                    ).exclude(pk=self.pk).update(position=F("position") - 1)

                super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # On delete, close the gap by decrementing positions greater than this one
        with transaction.atomic():
            pos = self.position
            space = self.space
            super().delete(*args, **kwargs)
            SpaceRole.objects.filter(space=space, position__gt=pos).update(position=F("position") - 1)

    def is_higher_than(self, other: "SpaceRole") -> bool:
        if other is None:
            return True
        return (self.position or 0) > (other.position or 0)

    def is_lower_than(self, other: "SpaceRole") -> bool:
        if other is None:
            return False
        return (self.position or 0) < (other.position or 0)

    def move_up(self):
        if self.position and self.position > 1:
            self.position -= 1
            self.save()

    def move_down(self):
        # max position is current count of roles in the space
        max_pos = SpaceRole.objects.filter(space=self.space).aggregate(max_pos=Max("position")).get("max_pos") or 0
        if self.position and self.position < max_pos:
            self.position += 1
            self.save()

    def move_to(self, new_position: int):
        self.position = new_position
        self.save()


class Channel(ResourceModel):
    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name="channels")
    name = models.CharField(max_length=64)
    position = models.IntegerField(validators=[MinValueValidator(1)], db_index=True)
    category = models.ForeignKey("Category", on_delete=models.SET_NULL, null=True, blank=True, related_name="channels")
    news = models.BooleanField(default=False)
    gdm = models.BooleanField(default=False)
    rdm = models.BooleanField(default=False)
    sysdm = models.BooleanField(default=False)
    last_message = models.ForeignKey("Message", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["space", "position"], name="unique_channel_position_per_space")
        ]
        ordering = ["position", "name"]

class Category(ResourceModel):
    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=64)
    position = models.IntegerField(validators=[MinValueValidator(1)], db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["space", "position"], name="unique_category_position_per_space")
        ]
        ordering = ["position", "name"]

class ChannelForwarder(ResourceModel):
    source_channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="forwarders")
    destination_channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="incoming_forwarders")

class GroupDM(ResourceModel):
    name = models.CharField(max_length=120)
    icon = models.URLField(blank=True, null=True)
    members = models.ManyToManyField("users.User", related_name="group_dms")
    owner = models.ForeignKey("users.User", on_delete=models.CASCADE)
    channel = models.OneToOneField(Channel, on_delete=models.CASCADE, related_name="group_dm", null=True, blank=True)

class DM(ResourceModel):
    user1 = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="dms_as_user1")
    user2 = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="dms_as_user2")
    channel = models.OneToOneField(Channel, on_delete=models.CASCADE, related_name="dm", null=True, blank=True)

class Message(ResourceModel):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey("users.User", on_delete=models.CASCADE)
    content = models.TextField(blank=True)
    attachments = models.JSONField(default=list, blank=True)
    reply_to = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="replies")
    mentions = models.ManyToManyField("users.User", related_name="mentioned_in")
    pinned_to_channel = models.BooleanField(default=False)

class MessageReadState(ResourceModel):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="read_states")
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="read_states")
    last_read_message = models.ForeignKey(Message, on_delete=models.SET_NULL, null=True, blank=True)
    mention_count = models.IntegerField(default=0)

class Friendship(ResourceModel):
    user1 = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="friendships_as_user1")
    user2 = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="friendships_as_user2")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user1", "user2"], name="unique_friendship"),
            models.CheckConstraint(check=~models.Q(user1=models.F("user2")), name="prevent_self_friendship")
        ]

class Blocks(ResourceModel):
    blocker = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="blocks_initiated")
    blocked = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="blocks_received")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["blocker", "blocked"], name="unique_block"),
            models.CheckConstraint(check=~models.Q(blocker=models.F("blocked")), name="prevent_self_block")
        ]

class UserRoleAssignment(ResourceModel):
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="space_roles")
    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name="user_roles")
    role = models.ForeignKey(SpaceRole, on_delete=models.CASCADE, related_name="assigned_users")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "space", "role"], name="unique_user_role_assignment")
        ]

class Invite(ResourceModel):
    code = models.CharField(max_length=64, unique=True, default=snowflaker, editable=False)
    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name="invites")
    channel = models.ForeignKey(Channel, on_delete=models.SET_NULL, null=True, blank=True, related_name="invites")
    inviter = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, related_name="sent_invites")
    expires_at = models.DateTimeField(blank=True, null=True)
    permanent = models.BooleanField(default=False)
    max_uses = models.IntegerField(blank=True, null=True)
    uses = models.IntegerField(default=0)
    roles_granted = models.ManyToManyField(SpaceRole, related_name="invites_granting_role")

class SpaceBan(ResourceModel):
    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name="bans")
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="space_bans")
    reason = models.TextField(blank=True)
    banned_by = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, related_name="issued_bans")
    expires_at = models.DateTimeField(blank=True, null=True)
    active = models.BooleanField(default=True)

class UserNote(ResourceModel):
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="notes")
    content = models.TextField(blank=True)
    created_by = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, related_name="created_notes")

class CustomEmoji(ResourceModel):
    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name="custom_emojis")
    name = models.CharField(max_length=64)
    url = models.URLField()
    creator = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, related_name="created_emojis")
    available = models.BooleanField(default=True)

class AuditLogEntry(ResourceModel):
    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name="audit_logs")
    action = models.CharField(max_length=64)
    performed_by = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, related_name="performed_audit_logs")
    details = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)

class Attachment(ResourceModel):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="attachments")
    url = models.URLField()
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size = models.IntegerField()
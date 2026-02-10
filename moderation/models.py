from django.db import models
from users.models import User
from koru.utils import ResourceModel, snowflaker
from .utils import recalc_standing, recalc_points

# Create your models here.
class UserViolation(ResourceModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="moderation_records")
    reason = models.TextField(blank=True)
    action = models.CharField(max_length=64)
    issued_at = models.DateTimeField(auto_now_add=True)
    issuing_moderator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="issued_violations")
    expires_at = models.DateTimeField(blank=True, null=True)
    expired = models.BooleanField(default=False)
    can_appeal = models.BooleanField(default=True)
    appealed = models.BooleanField(default=False)
    # 0 = "No appeal" - 1 = "Pending response" - 2 = "Denied" - 3 = "Accepted"
    appeal_status = models.IntegerField(default=0)
    active = models.BooleanField(default=True)
    standing_point_worth = models.IntegerField(default=5)

    suspended = None
    deleted = None

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if self.pk is None:
            pass
        if self.pk and self.expires_at and self.expires_at < models.functions.Now():
            self.expired = True
            self.active = False
        if self.pk and self.active and self.expired:
            self.active = False
        if self.pk and self.appealed == True and self.appeal_status == 3:
            self.active = False
        super().save(*args, **kwargs)
        recalc_points(self.user)
        recalc_standing(self.user)


class UserRecord(models.Model):
    id = models.CharField(max_length=64, primary_key=True, default=snowflaker, editable=False, unique=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="moderation_record")
    # Semi-carbon-copy of discord's standing system basically.
    # 0 = "All good" / No active violations
    # 1 = "Warning" / Minor violation with no actual punishment
    # 2 = "Limited" / Temporary loss of some features
    # 3 = "Very limited" / Limited, but longer!
    # 4 = "At risk"...of being suspended
    # 5 = "Suspended" / Suspended from the platform for a period of time
    standing = models.IntegerField(default=0)
    # The only game where the more points you have the worse you are!
    # 0-4 = "Good standing" / No active violations
    # 5-15 = "Warning" / Minor violation with no actual punishment
    # 16-20 = "Limited" / Temporary loss of some features
    # 21-25 = "Very limited" / Limited, but longer!
    # 26-30 = "At risk"...of being suspended
    # 31-35 = "Suspended" / Suspended from the platform. Can log in but can't change anything.
    # 36+ = Suspended, but cannot log in.
    # Standing points expire with the violations they are attached to.
    standing_points = models.IntegerField(default=0)
    violations = models.ManyToManyField(UserViolation, related_name="records", blank=True)
from django.db import models
from .models import UserRecord, UserViolation
from users.models import User

def recalc_standing(user: User):
    record, created = UserRecord.objects.get_or_create(user=user)
    active_violations = user.moderation_records.filter(expires_at__gt=models.functions.Now(), appealed=False)
    total_points = sum(v.standing_point_worth for v in active_violations)

    record.standingPts = total_points

    if total_points >= 36:
        record.standing = 5
    elif total_points >= 31:
        record.standing = 4
    elif total_points >= 26:
        record.standing = 3
    elif total_points >= 21:
        record.standing = 2
    elif total_points >= 16:
        record.standing = 1
    else:
        record.standing = 0

    record.save()

def recalc_points(user: User):
    violations = UserViolation.objects.exclude(active=False).filter(user=user)
    total_points = sum(v.standing_point_worth for v in violations)
    record, created = UserRecord.objects.get_or_create(user=user)
    record.standing_points = total_points
    record.save()
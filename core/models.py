from django.db import models

class Space(models.Model):
    name = models.CharField(max_length=64)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey("allauth.account.models.User", on_delete=models.CASCADE)
    members = models.ManyToManyField("allauth.account.models.User", related_name="spaces")
    features = models.JSONField(default=dict)
from django.db import models
from snowflakekit import SnowflakeGenerator, SnowflakeConfig
from django.forms import ValidationError

def snowflaker():
    config = SnowflakeConfig(
        epoch=1767225600000,  # January 1, 2026
        worker_id=2,
        time_bits=39,
        node_bits=5,
        worker_bits=8
    )
    generator = SnowflakeGenerator(config)
    return generator.generate()

class ResourceModel(models.Model):
    id = models.CharField(max_length=64, primary_key=True, default=snowflaker, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # May go unused in some resources
    suspended = models.BooleanField(default=False)
    deleted = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = snowflaker()
        # If this entry is being updated we need to throw an error if the snowflake is being changed
        elif self.pk and self.id != self.__class__.objects.get(pk=self.pk).id:
            raise ValidationError("ID cannot be changed once set.")

        super().save(*args, **kwargs)
    
    class Meta:
        abstract = True
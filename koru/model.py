from django import models
from snowflakekit import SnowflakeGenerator, SnowflakeConfig
from django.forms import ValidationError

def snowflake_from_timestamp(timestamp):
    config = SnowflakeConfig(
        epoch=1767225600000,  # January 1, 2026
        worker_id=2,
        time_bits=39,
        node_bits=5,
        worker_bits=8
    )
    generator = SnowflakeGenerator(config)
    return generator.generate(timestamp)

class ResourceModel(models.Model):
    # Snowflake ID. This is what the user sees.
    snowflake = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # May go unused in some resources
    suspended = models.BooleanField(default=False)
    deleted = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.snowflake:
            self.snowflake = snowflake_from_timestamp(int(self.created_at.timestamp() * 1000))
        # If this entry is being updated we need to throw an error if the snowflake is being changed
        elif self.pk and self.snowflake != self.__class__.objects.get(pk=self.pk).snowflake:
            raise ValidationError("Snowflake cannot be changed once set.")

        super().save(*args, **kwargs)
    
    class Meta:
        abstract = True
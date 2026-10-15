from django.db import models, transaction
from django.contrib.auth.models import AbstractUser
from datetime import date, timedelta
from django.utils import timezone
import uuid

# Create your models here.
class User(AbstractUser):
    username = None
    email = models.EmailField(max_length=254, unique=True)
    password = models.CharField(max_length=254, blank=True, null=True)
    api_key = models.UUIDField(default=uuid.uuid4, unique=True)
    requests_today = models.IntegerField(default=0)
    last_reset = models.DateField(default=date.today)
    dev_note = models.TextField(blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def reset_limits(self):
        if self.last_reset < date.today():
            with transaction.atomic():
                usage_data = UsageData(
                    user = self,
                    date = self.last_reset,
                    usage = self.requests_today
                )
                usage_data.save()
                self.requests_today = 0
                self.last_reset = date.today()
                self.save()


class UsageData(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField()
    usage = models.IntegerField(default=0)

    class Meta:
        unique_together = ('user', 'date') # Prevents duplicate daily logs

def otp_expiry():
    return timezone.now() + timedelta(minutes=5)

    
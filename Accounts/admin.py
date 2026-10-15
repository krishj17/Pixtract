from django.contrib import admin
from Accounts.models import User, UsageData
# Register your models here.

class UserDisplay(admin.ModelAdmin):
    list_display = ["id", "email", "requests_today", "last_reset"]

admin.site.register(User, UserDisplay)
admin.site.register(UsageData)

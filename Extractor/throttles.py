from rest_framework.throttling import SimpleRateThrottle
from Accounts.models import User
from datetime import date, timedelta
from django.utils import timezone
from django.core.cache import cache

class UnsignedThrottle(SimpleRateThrottle):
    scope = "unsigned"

    def get_cache_key(self, request, view):
        if request.data.get("api_key"):
            return None
        return self.get_ident(request)
    
    def allow_request(self, request, view):
        now = timezone.datetime.now()
        midnight = timezone.datetime.combine(now.date() + timedelta(days=1), timezone.datetime.min.time())
        # Dynamically set the duration for this specific request check
        self.duration = int((midnight - now).total_seconds())

        return super().allow_request(request, view)


def get_user_id_from_api_key(api_key):
    # Check if user_id is cached.
    cache_key = f"api_user_{api_key}"
    user_id = cache.get(cache_key)

    if user_id is not None:
        print("used cache")
        return user_id
    
    # If not, fetch user and cache the id
    try:
        user=User.objects.get(api_key=api_key)
        print("db hit!")
        cache.set(cache_key, user.id, timeout=7200) # cache for 2 hour
        return user.id
    
    except User.DoesNotExist as e:
        return None


class SignedThrottle(SimpleRateThrottle):
    scope = "signed"

    def get_cache_key(self, request, view):
        api_key = request.data.get("api_key")

        # Skip if NOT signed
        if not api_key:
            return None

        user_id = get_user_id_from_api_key(api_key)
        return f"signed_{user_id}"
    
    def allow_request(self, request, view):
        now = timezone.datetime.now()
        midnight = timezone.datetime.combine(now.date() + timedelta(days=1), timezone.datetime.min.time())
        # Dynamically set the duration for this specific request check
        self.duration = int((midnight - now).total_seconds())
        
        return super().allow_request(request, view)


class BurstSignedThrottle(SimpleRateThrottle):
    scope = "signed_burst"

    def get_cache_key(self, request, view):
        api_key = request.data.get("api_key")
        if not api_key:
            return None
        return f"burst_{api_key}"



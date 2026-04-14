from rest_framework.throttling import BaseThrottle
from django.core.cache import cache

UNSIGNED_DAILY_LIMIT = 50

class UnsignedRateThrottle(BaseThrottle):

    def allow_request(self, request, view):
        # Signed users are handled by the view's own limit check
        if request.data.get("api_key"):
            return True

        ip = self.get_ident(request)
        key = f"unsigned_requests_{ip}"
        count = cache.get(key, 0)

        if count >= UNSIGNED_DAILY_LIMIT:
            return False

        cache.set(key, count + 1, timeout=86400)  # 86400s = 24 hours
        return True

    def wait(self):
        return None
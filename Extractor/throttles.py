from datetime import datetime, time, timedelta
from uuid import UUID
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework.throttling import BaseThrottle
from Accounts.models import User


def parse_rate(rate):
    count, period = rate.split("/")
    duration = {"s": 1, "m": 60, "h": 3600, "d": 86400}[period[0]]
    return int(count), duration


def get_api_user(api_key):
    """Return the active user's ID, using cache to avoid repeated DB queries."""
    try:
        api_key = str(UUID(str(api_key)))
    except Exception:
        return None

    cache_key = f"api_user_{api_key}"
    user_id = cache.get(cache_key)
    if user_id is not None:
        return user_id

    user = User.objects.filter(api_key=api_key, is_active=True).only("id").first()
    if user is None:
        return None

    cache.set(cache_key, user.id, timeout=7200)
    return user.id


class RequestThrottle(BaseThrottle):

    def __init__(self):
        rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
        self.unsigned_rate = parse_rate(rates["unsigned"])
        self.signed_rate = parse_rate(rates["signed"])
        self.burst_rate = parse_rate(rates["signed_burst"])
        self.retry_after = None

    def allow_request(self, request, view):
        now = timezone.now()

        # Identify the user, if an API key was provided.
        api_key = request.data.get("api_key")
        user_id = get_api_user(api_key) if api_key else None

        request.is_api_authenticated = user_id is not None
        request.api_key_invalid = bool(api_key and user_id is None)

        if user_id is not None:
            request.api_user_id = user_id

            # Authenticated requests have daily and burst limits.
            limits = [
                (f"throttle_signed_{user_id}_{timezone.localdate(now)}", self.signed_rate, self.seconds_until_midnight(now)),
                (f"throttle_burst_{user_id}", self.burst_rate, self.burst_rate[1])
            ]
        else:
            # Anonymous requests have a daily IP-based limit.
            ip = self.get_ident(request)

            limits = [
                (
                    f"throttle_unsigned_{ip}_{timezone.localdate(now)}",
                    self.unsigned_rate,
                    self.seconds_until_midnight(now)
                )
            ]

        # Reject the request if any applicable limit is exceeded.
        retry_times = []

        for key, rate, ttl in limits:
            retry = self.check_limit(key, rate, ttl, now.timestamp())

            if retry is not None:
                retry_times.append(retry)

        if retry_times:
            self.retry_after = min(retry_times)
            return False

        return True

    @staticmethod
    def check_limit(key, rate, ttl, now):
        """Record a request or return the number of seconds to wait."""
        max_requests, window = rate

        history = cache.get(key, [])

        # Keep only requests inside the current time window.
        history = [
            timestamp
            for timestamp in history
            if timestamp > now - window
        ]

        if len(history) >= max_requests:
            return max(0, history[0] + window - now)

        history.append(now)
        cache.set(key, history, timeout=max(1, ttl))

        return None

    @staticmethod
    def seconds_until_midnight(now):
        local_now = timezone.localtime(now)
        tomorrow = local_now.date() + timedelta(days=1)

        midnight = timezone.make_aware(
            datetime.combine(tomorrow, time.min),
            local_now.tzinfo,
        )

        return max(1, int((midnight - now).total_seconds()))

    def wait(self):
        return self.retry_after

    @staticmethod
    def get_ident(request):
        """Get the client's IP address, accounting for configured proxies."""
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        num_proxies = settings.REST_FRAMEWORK.get("NUM_PROXIES")

        if forwarded and num_proxies is not None:
            addresses = forwarded.split(",")
            if num_proxies:
                return addresses[-num_proxies].strip()
            return request.META.get("REMOTE_ADDR", "")

        if forwarded:
            return forwarded.split(",")[0].strip()

        return request.META.get("REMOTE_ADDR", "")


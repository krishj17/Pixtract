from django.contrib.auth.backends import ModelBackend
from Accounts.models import User

# Custion authenticate logic for email.
class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        email = username  # Django passes it as username
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return None

        if user.password and user.check_password(password):
            return user
        return None
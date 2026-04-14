from django.urls import path
from Accounts.views import dashboard, auth, regen_key, register_email, verify_otp, set_password, user_login, user_logout
urlpatterns = [
    # Pages urls:
    path("", dashboard, name="dashboard"),
    path("auth", auth, name="auth"),

    # Other urls:
    path("register_email", register_email, name="register_email"),
    path("verify_otp", verify_otp, name="verify_otp"),
    path("set_password", set_password, name="set_password"),
    path("login", user_login, name="login"),
    path("logout", user_logout, name="logout"),
    
    path("regen_key", regen_key, name="regen_key"),
]

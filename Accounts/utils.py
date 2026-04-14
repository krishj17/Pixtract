from django.http import JsonResponse
from django.utils import timezone
from Accounts.models import OTP


def check_otp(request) -> dict:
    email = request.POST.get("email").strip()
    otp = request.POST.get("otp").strip()

    otp_obj = OTP.objects.filter(email=email).latest("id")
    
    if otp_obj is None:
        return {"status": "error", "error": "No OTP found", "code":404}
    
    # check expiry
    if timezone.now() > otp_obj.expires_at:
        return {"status": "error", "error": "OTP expired", "code":410}
    
     # check OTP
    if otp_obj.otp_hash != otp:
        return {"status": "error", "error": "Invalid OTP", "code":400}
    
    return {"status":"success", "message":"OTP Verified.", "code":200}
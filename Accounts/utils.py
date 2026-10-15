from django.core.cache import cache


def check_otp(request) -> dict:
    email = request.POST.get("email")
    otp = request.POST.get("otp")

    if not email or not otp:
        return {"status": "error", "error": "Email and OTP are required", "code": 400}

    otp_cache = cache.get(f'otp_{email}')
    if otp_cache is None:
        return {"status": "error", "error": "OTP expired or not found", "code": 404}
    
    # check OTP
    if str(otp_cache) != otp:
        return {"status": "error", "error": "Invalid OTP", "code":400}
    
    return {"status":"success", "message":"OTP Verified.", "code":200}
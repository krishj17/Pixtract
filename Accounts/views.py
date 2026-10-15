import uuid

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.middleware.csrf import get_token
from django.core.cache import cache
from random import randint

from Accounts.models import User
from Accounts.utils import check_otp


@login_required(login_url="auth")
def dashboard(request):
    return render(request, "dashboard.html")

def auth(request):
    return render(request, "auth.html")


def register_email(request):
    try:
        email = request.POST.get('email').strip()

        # check if email exist:
        if User.objects.filter(email=email).exists():
            return JsonResponse({"status":"error", "error":"User with the email already exists."}, status=409) 

        # Send otp:
        otp = randint(1000,9999)
        cache.set(key=f"otp_{email}", value=otp, timeout=300) # expires in 5 minutes.
        send_mail("Pixtract OTP", f"Dear User your OTP for registeration is: {otp}", settings.EMAIL_HOST_USER, [email])

        return JsonResponse({"status":"success", "message":"otp sent.", "user_email": email}, status=200)

    except Exception as e:
        print("ERROR IN register_email: ", e)
        return JsonResponse({"status":"error", "error":str(e)}, status=500) 


def verify_otp(request):
    response = check_otp(request)

    if response.get("status") == "error":
        status_code = response.pop("code")
        return JsonResponse(response, status=status_code)
    
    # Create User Object.
    user, created = User.objects.get_or_create(
        email = request.POST.get("email")
    )
    
    login(request, user)
    new_csrf = get_token(request)
    print("new_csrf token:--",new_csrf)

    if created:
        return JsonResponse({
            "status": "success", 
            "message": "Email verified, Account Created.", 
            "new_csrf":new_csrf, 
            "is_new_user": created
        }, status=201)
    else:
        return JsonResponse({
            "status": "success", 
            "message": "Email verified, Login Successful.", 
            "new_csrf":new_csrf, 
            "is_new_user": created
        }, status=200)


@login_required(login_url="auth")
def set_password(request):
    password = request.POST.get('password').strip()
    confirm_password = request.POST.get('confirm_password').strip()

    # Validate empty input
    if not password or not confirm_password:
        return JsonResponse({"status": "error", "error": "Fields cannot be empty."}, status=400)
    
    # Check match
    if password != confirm_password:
        return JsonResponse({"status": "error", "error": "Both the passwords should be same."}, status=400)
    
    # Validate Password Complexity (Django default)
    try:
        validate_password(password)
    except ValidationError as e:
        return JsonResponse({"status": "error", "error": list(e)}, status=400)

    print("password to set: ", password)

    user = request.user
    user.set_password(password)
    user.save()

    update_session_auth_hash(request, user)

    return JsonResponse({"status": "success", "message": "Password set Successfully."}, status=200)


def user_login(request):
    email = request.POST.get("email").strip()
    password = request.POST.get("password").strip()
    print(email, password)
    if email == "" or password == "":
        return JsonResponse({"status":"error", "error":"Please provide both email and password"}, status=400)
    
    try:
        # Check if Email exist.
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return JsonResponse({"status":"error", "error":"Account with the Email dosen't exist."}, status=404)
        
        # If no password, send otp email.
        if user.password is None:
            # Send otp:
            otp = randint(1000,9999)
            cache.set(key=f"otp_{email}", value=otp, timeout=300) # expires in 5 minutes.
            send_mail("Pixtract OTP", f"Dear User your OTP for Login is: {otp}", settings.EMAIL_HOST_USER, [email])

            return JsonResponse({"status":"success", "message":"Login OTP Sent to your Email.", "user_email": email}, status=200)

        # Login user if everything is ok.
        user = authenticate(request, username=email, password=password)
        if user:
            login(request, user)
            return JsonResponse({"status":"success", "message":"Login Successful."}, status=200)
        else:
            return JsonResponse({"status":"error", "error":"Invalid email or password."}, status=401)
        
    except Exception as e:
        return JsonResponse({"status":"error", "error":str(e)}, status=400)
        

@login_required(login_url="auth")
def user_logout(request):
    logout(request)
    return redirect(auth)
    

@login_required(login_url="auth")
def regen_key(request):
    request.user.api_key = uuid.uuid4()
    request.user.save()
    return JsonResponse({"status":"success", "api_key": str(request.user.api_key)}, status = 200)


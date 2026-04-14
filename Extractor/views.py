from rest_framework.views import APIView
from rest_framework.response import Response
from Extractor.scraper import extract
from Extractor.serializers import ExtractRequestSerializer
from Extractor.utils import manage_result
from Accounts.models import User
from django.db.models import F
from Extractor.throttles import UnsignedRateThrottle

class ExtractView(APIView):

    throttle_classes = [UnsignedRateThrottle]

    def post(self, request):
        # Get user_type and user. 
        user_info = get_user_info(request)
        if user_info.get("status") == "error":
            return Response({"status":"error", "error":user_info.get("error")}, status=400)

        # Check if limits are Available.
        user = user_info.get("user")
        if user:
            limit = 500
            if user.requests_today > limit:
                return Response({"status": "error", "error": "Daily limit reached. Resets at midnight."}, status=429)

        # Serialize the data and fetch.
        serializer = ExtractRequestSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            extracted_result = extract(data.get('url'), False, data.get('screenshot'))

            final_result = manage_result(
                result = extracted_result, 
                user_type = user_info.get("user_type"),
                fields = data.get('fields')
            )

            # Increment request_today.
            if user:
                user.requests_today = F('requests_today') + 1
                user.save(update_fields=['requests_today'])

            return Response({"status":"success", "site":final_result}, status=200)
        else:
            return Response({"status":"error", "error": serializer.errors}, status=400)


def get_user_info(request):
    api_key = request.data.get("api_key")
    if api_key is None:
        return {"status":"success", "user_type":"unsigned"}
    
    try:
        user = User.objects.get(api_key=api_key)
        user.reset_limits() # if last_date < Today
        return {"status":"success", "user_type":"signed", "user":user}
    except User.DoesNotExist:
        return {"status":"error", "error":"Invalid Api Key"}
    except Exception as e:
        return {"status":"error", "error":str(e)}
    

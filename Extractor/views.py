from rest_framework.views import APIView
from rest_framework.response import Response
from Extractor.scraper import extract
from Extractor.serializers import ExtractRequestSerializer
from Extractor.utils import reorder_result  
from Extractor.constants import ALL_FIELDS, SIGNED_ONLY_KEYS
from Extractor.throttles import RequestThrottle

class ExtractView(APIView):

    throttle_classes = [RequestThrottle]

    def post(self, request):
        if getattr(request, "api_key_invalid", False):
            return Response({"status": "error", "error": "Invalid API key."}, status=401)

        serializer = ExtractRequestSerializer(data=request.data)

        if serializer.is_valid():

            data = serializer.validated_data

            # Check if user is signed or unsigned.
            is_api_user = getattr(request, 'is_api_authenticated', False)
    
            # Invalidate non loggedin user screenshot requests.
            if data.get('screenshot') and not is_api_user:
                return Response({"status":"error", "error": "Please Signup to access screenshot feature!"}, status=400)
            if data.get('fields') and not is_api_user:
                return Response({"status":"error", "error": "Please Signup to access fields feature!"}, status=400)
            
            # Determine fields BEFORE hitting the scraper
            if is_api_user:
                fields = set(data.get('fields')) if data.get('fields') else set(ALL_FIELDS) 
                # If screenshot=true is not explicitly set then remove screenshot field
                if not data.get('screenshot'): 
                    fields.discard("screenshot")
            else:
                fields = set(ALL_FIELDS) - SIGNED_ONLY_KEYS 

            # Extract the metadata.
            extracted_result = extract(
                url = data.get('url'), 
                fields = fields,
            )
            # print("Extracted Result:--- ", extracted_result)
            
            # Remove empty fields and Organize output fields.
            final_result = reorder_result(
                result = extracted_result, 
                is_api_user = is_api_user,
                requested_fields=fields
            )

            return Response({"status":"success", "site":final_result}, status=200)
        else:
            return Response({"status":"error", "error": serializer.errors}, status=400)


    

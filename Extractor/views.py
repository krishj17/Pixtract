from rest_framework.views import APIView
from rest_framework.response import Response
from Extractor.scraper import extract
from Extractor.serializers import ExtractRequestSerializer
from Extractor.utils import manage_result
from Extractor.throttles import UnsignedThrottle, SignedThrottle, BurstSignedThrottle

class ExtractView(APIView):

    throttle_classes = [UnsignedThrottle, SignedThrottle, BurstSignedThrottle]

    def post(self, request):
        # Serialize the data and fetch.
        serializer = ExtractRequestSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            extracted_result = extract(data.get('url'), False, data.get('screenshot'))

            final_result = manage_result(
                result = extracted_result, 
                # user_type = user_info.get("user_type"),
                fields = data.get('fields')
            )

            return Response({"status":"success", "site":final_result}, status=200)
        else:
            return Response({"status":"error", "error": serializer.errors}, status=400)


    

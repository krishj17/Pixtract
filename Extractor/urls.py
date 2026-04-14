from django.urls import path
from Extractor.views import ExtractView

urlpatterns = [
    path("", ExtractView.as_view())   
]
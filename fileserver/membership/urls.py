from django.urls import re_path
from rest_framework_jwt.views import obtain_jwt_token, verify_jwt_token

from . import views

# URL patterns
urlpatterns = [
    re_path("register/", views.UserCreateAPIView.as_view(), name="register"),
    re_path("login/", obtain_jwt_token),
    re_path("status/", views.UserStatusView.as_view(), name="status")
]

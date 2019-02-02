from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect
from rest_framework import generics, renderers, response, status, views
from rest_framework_msgpack.renderers import MessagePackRenderer

from . import models
from . import permissions
from . import serializers


# User registration API
class UserCreateAPIView(generics.CreateAPIView):
    serializer_class = serializers.UserCreateSerializer
    queryset = User.objects.all()


""" # User login API
class UserLoginAPIView(views.APIView):
    serializer_class = serializers.UserLoginSerializer

    def post(self, request, *args, **kwargs):
        data = request.data
        serializer = serializers.UserLoginSerializer(data=data)

        if serializer.is_valid(raise_exception=True):
            new_data = serializer.data

            user = authenticate(request, username=new_data["username"], password=data["password"])
            if user is not None:
                login(request, user)

            if "remain_in" not in request.data or not request.data["remain_in"]:
                request.session.set_expiry(0)

            return response.Response(new_data, status=status.HTTP_200_OK)
        else:
            return response.Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST) """


# User Config API
class UserConfigView(generics.RetrieveUpdateAPIView):
    permission_classes = (permissions.FileserverPermission, )
    serializer_class = serializers.UserConfigSerializer
    queryset = models.UserConfig.objects.all()
    http_method_names = [method for method in generics.RetrieveUpdateAPIView.http_method_names if method not in ["put"]]

    def get_object(self):
        queryset = self.get_queryset()
        obj = get_object_or_404(queryset, user=self.request.user)
        return obj


# User Status API
class UserStatusView(views.APIView):
    def get(self, request):
        if request.user.is_authenticated and models.AuthGroup.user_is_auth(request.user):
            fs_auth = True
        else:
            fs_auth = False

        data = {"authenticated": fs_auth}
        if fs_auth:
            data["user"] = {"username": request.user.username, "full_name": request.user.first_name + " " + request.user.last_name}
        return response.Response(data, status=status.HTTP_200_OK)


""" # User Logout API
class UserLogoutView(views.APIView):
    def get(self, request):
        logout(request)
        return UserStatusView.get(self, request) """

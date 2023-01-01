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


# User Status API
class UserStatusView(views.APIView):
    def get(self, request):
        authgroups, user = permissions.get_request_authgroups(request)
        if authgroups.exists():
            fs_auth = True
        else:
            fs_auth = False

        data = {"authenticated": fs_auth}
        if fs_auth:
            if user is not None:
                data["user"] = {"username": request.user.username, "full_name": request.user.first_name + " " + request.user.last_name}
                data["config"] = serializers.UserConfigSerializer(models.UserConfig.objects.filter(user=request.user.id).first()).data
            else:
                data["user"] = {"username": None, "full_name": "Anonymous User"}
                data["config"] = models.DEFAULT_USER_CONFIG
            data["auth_groups"] = serializers.AuthGroupSerializer(authgroups, many=True).data
        return response.Response(data, status=status.HTTP_200_OK)

    def patch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return response.Response({"detail": "Not authenticated."}, status=status.HTTP_403_FORBIDDEN)

        if "config" not in request.data:
            return response.Response({"detail": "Config data not provided."}, status=status.HTTP_400_BAD_REQUEST)

        partial = kwargs.pop('partial', False)
        instance = models.UserConfig.objects.filter(user=request.user.id).first()
        serializer = serializers.UserConfigSerializer(instance, data=request.data["config"], partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return self.get(request)

# TODO test all this

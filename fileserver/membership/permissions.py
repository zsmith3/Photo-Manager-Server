from django.conf import settings
from rest_framework import exceptions, permissions
from rest_framework_jwt.authentication import JSONWebTokenAuthentication

from . import models


# Permission class for fileserver API access
class FileserverPermission(permissions.BasePermission):
    def has_permission(self, request, view=None):
        # No auth required in debug mode
        if settings.DEBUG and not settings.USE_AUTH_IN_DEBUG:
            return True

        if request.user.is_authenticated:
            user = request.user
        else:
            try:
                auth = JSONWebTokenAuthentication().authenticate(request)
            except exceptions.AuthenticationFailed:
                return False

            if auth is None:
                return False
            else:
                user = auth[0]

        if models.AuthGroup.user_is_admin(user):
            return True
        elif models.AuthGroup.user_is_auth(user):
            if request.method in permissions.SAFE_METHODS:
                return True

        return False

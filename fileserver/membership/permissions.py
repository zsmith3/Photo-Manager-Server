from django.conf import settings
from rest_framework import exceptions, permissions
from rest_framework_jwt.authentication import JSONWebTokenAuthentication

from . import models


# Get user from request object
def get_request_user(request):
    try:
        auth = JSONWebTokenAuthentication().authenticate(request)
    except exceptions.AuthenticationFailed:
        return None

    if auth is None:
        return None
    else:
        return auth[0]


# Permission class for fileserver API access
class FileserverPermission(permissions.BasePermission):
    def has_permission(self, request, view=None):
        user = get_request_user(request)
        if user is None:
            if settings.DEBUG and not settings.USE_AUTH_IN_DEBUG:
                return True
            else:
                return False

        if models.AuthGroup.user_is_admin(user):
            return True
        elif models.AuthGroup.user_is_auth(user):
            if request.method in permissions.SAFE_METHODS:
                return True

        return False

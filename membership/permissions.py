from rest_framework import permissions

from . import models


# Permission class for fileserver API access
class FileserverPermission(permissions.BasePermission):
    def has_permission(self, request, view=None):
        if request.user.is_authenticated:
            if models.AuthGroup.user_is_admin(request.user):
                return True
            elif models.AuthGroup.user_is_auth(request.user):
                if request.method in permissions.SAFE_METHODS:
                    return True

        return False

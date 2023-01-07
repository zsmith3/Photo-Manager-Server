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


# Get request auth groups (from user and/or url)
def get_request_authgroups(request):
    user = get_request_user(request)
    if user is not None:
        auth_groups = models.AuthGroup.objects.filter(group__in=user.groups.all())
    else:
        auth_groups = models.AuthGroup.objects.none()

    if "auth" in request.GET and request.GET["auth"]:
        code = request.GET["auth"]
        group_qs = models.AuthGroup.objects.filter(token=code, can_link=True)
        if group_qs.exists():
            auth_groups |= group_qs

    return auth_groups, user


# Permission class for fileserver access, with customisable access for non-admins
def getLinkPermissions(allowed_methods):
    class LinkPermission(permissions.BasePermission):
        def has_permission(self, request, view=None):
            authgroups, user = get_request_authgroups(request)
            print(authgroups, user, request.GET)

            if settings.DEBUG and not settings.USE_AUTH_IN_DEBUG:
                return True

            if request.method in permissions.SAFE_METHODS or request.method in allowed_methods:
                return authgroups.exists()

            if user is not None:
                return models.AuthGroup.user_is_admin(user)
            else:
                return False

    return LinkPermission


FileserverPermission = getLinkPermissions([])

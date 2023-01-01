import secrets
from django.db import models
from django.contrib.auth.models import User, Group


# Authentication user group
class AuthGroup(models.Model):
    group = models.OneToOneField(Group, related_name="auth", on_delete=models.CASCADE)
    token = models.TextField(max_length=64, default=secrets.token_hex)
    can_link = models.BooleanField(default=False)

    def __str__(self):
        return str(self.group.name)

    @staticmethod
    def user_is_auth(user):
        if AuthGroup.user_is_admin(user):
            return True

        auth = AuthGroup.objects.filter(id=1).first()
        return auth.group in user.groups.all()

    @staticmethod
    def user_is_admin(user):
        admin = AuthGroup.objects.filter(id=2).first()
        return admin.group in user.groups.all()


def create_auth_group(sender, instance, created, **kwargs):
    if created:
        AuthGroup.objects.create(group=instance)


models.signals.post_save.connect(create_auth_group, sender=Group)


# User configuration settings
class UserConfig(models.Model):
    user = models.OneToOneField(User, related_name="config", on_delete=models.CASCADE)

    SETTINGS = {
        "thumb_scale": {
            "min": 0,
            "max": 1,
            "default": {
                "desktop": 0.4,
                "mobile": 0.2
            }
        },
        "page_size": {
            "options": [(x, str(x)) for x in [10, 25, 50, 100, 200, 500, 1000]],
            "default": {
                "desktop": "100",
                "mobile": "25"
            }
        }
    }

    desktop_thumb_scale = models.FloatField(default=SETTINGS["thumb_scale"]["default"]["desktop"])
    mobile_thumb_scale = models.FloatField(default=SETTINGS["thumb_scale"]["default"]["mobile"])
    desktop_page_size = models.PositiveSmallIntegerField(choices=SETTINGS["page_size"]["options"], default=SETTINGS["page_size"]["default"]["desktop"])
    mobile_page_size = models.PositiveSmallIntegerField(choices=SETTINGS["page_size"]["options"], default=SETTINGS["page_size"]["default"]["mobile"])

    def __str__(self):
        return "Config for %s" % str(self.user)


DEFAULT_USER_CONFIG = {
    "desktop_thumb_scale": UserConfig.SETTINGS["thumb_scale"]["default"]["desktop"],
    "mobile_thumb_scale": UserConfig.SETTINGS["thumb_scale"]["default"]["mobile"],
    "desktop_page_size": UserConfig.SETTINGS["page_size"]["default"]["desktop"],
    "mobile_page_size": UserConfig.SETTINGS["page_size"]["default"]["mobile"],
}


def create_user_config(sender, instance, created, **kwargs):
    if created:
        UserConfig.objects.create(user=instance)


models.signals.post_save.connect(create_user_config, sender=User)

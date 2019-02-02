import secrets
from django.db import models
from django.contrib.auth.models import User, Group


# Authentication user group
class AuthGroup(models.Model):
    group = models.OneToOneField(Group, related_name="auth", on_delete=models.CASCADE)
    token = models.TextField(max_length=64, default=secrets.token_hex)

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


# Authentication user group
class UserConfig(models.Model):
    user = models.OneToOneField(User, related_name="config", on_delete=models.CASCADE)

    SETTINGS = {
        "thumb_scale": {
            "min": 50,
            "max": 300,
            "default": {
                "desktop": 150,
                "mobile": 100
            }
        },
        "select_mode": {
            "options": ((0, "Standard"), (1, "View"), (2, "Select")),
            "default": {
                "desktop": 0,
                "mobile": 1
            }
        },
        "fpp": {
            "options": (("10", "10"), ("25", "25"), ("50", "50"), ("100", "100"), ("200", "200"), ("500", "500"), ("inf", "Unlimited")),
            "default": {
                "desktop": "50",
                "mobile": "25"
            }
        },
        "show_filterBar": {
            "default": {
                "desktop": False,
                "mobile": False
            }
        },
        "show_toolBar": {
            "default": {
                "desktop": True,
                "mobile": True
            }
        },
        "show_infoColumn": {
            "default": {
                "desktop": False,
                "mobile": False
            }
        }
    }

    desktop_thumb_scale = models.PositiveIntegerField(default=SETTINGS["thumb_scale"]["default"]["desktop"])
    mobile_thumb_scale = models.PositiveIntegerField(default=SETTINGS["thumb_scale"]["default"]["mobile"])
    desktop_select_mode = models.PositiveIntegerField(choices=SETTINGS["select_mode"]["options"], default=SETTINGS["select_mode"]["default"]["desktop"])
    mobile_select_mode = models.PositiveIntegerField(choices=SETTINGS["select_mode"]["options"], default=SETTINGS["select_mode"]["default"]["mobile"])
    desktop_fpp = models.CharField(choices=SETTINGS["fpp"]["options"], default=SETTINGS["fpp"]["default"]["desktop"], max_length=3)
    mobile_fpp = models.CharField(choices=SETTINGS["fpp"]["options"], default=SETTINGS["fpp"]["default"]["mobile"], max_length=3)

    desktop_show_filterBar = models.BooleanField(default=SETTINGS["show_filterBar"]["default"]["desktop"])
    mobile_show_filterBar = models.BooleanField(default=SETTINGS["show_filterBar"]["default"]["mobile"])
    desktop_show_toolBar = models.BooleanField(default=SETTINGS["show_toolBar"]["default"]["desktop"])
    mobile_show_toolBar = models.BooleanField(default=SETTINGS["show_toolBar"]["default"]["mobile"])
    desktop_show_infoColumn = models.BooleanField(default=SETTINGS["show_infoColumn"]["default"]["desktop"])
    mobile_show_infoColumn = models.BooleanField(default=SETTINGS["show_infoColumn"]["default"]["mobile"])

    def __str__(self):
        return "Config for %s" % str(self.user)


def create_user_config(sender, instance, created, **kwargs):
    if created:
        UserConfig.objects.create(user=instance)


models.signals.post_save.connect(create_user_config, sender=User)

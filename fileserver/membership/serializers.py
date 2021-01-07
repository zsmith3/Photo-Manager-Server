from django.contrib.auth.models import User, Group
from django.db.models import Q
from rest_framework import serializers
from rest_framework.authtoken.models import Token

import user_agents
import json

from . import models


# Registration API serializer
class UserCreateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(label="Email Address")
    confirm_password = serializers.CharField(max_length=128, required=True, allow_blank=False, write_only=True, style={"input_type": "password"}, label="Confirm Password")
    token = serializers.CharField(max_length=64, required=True, allow_blank=False, write_only=True)

    class Meta:
        model = User
        fields = ("username", "email", "password", "confirm_password", "first_name", "last_name", "token")
        extra_kwargs = {"password": {"write_only": True}}

    # Check email has not been used before
    def validate_email(self, value):
        user_qs = User.objects.filter(email=value)
        if user_qs.exists():
            raise serializers.ValidationError("There is already an account with this email address.")

        return value

    # Check passwords match
    def validate_confirm_password(self, value):
        password1 = self.get_initial().get("password")
        if password1 != value:
            raise serializers.ValidationError("The passwords entered do not match.")

        return value

    # Check token exists
    def validate_token(self, value):
        token_qs = models.AuthGroup.objects.filter(token=value)
        if token_qs.exists():
            self.group = token_qs.first().group
        else:
            raise serializers.ValidationError("Invalid token supplied.")

        return value

    # Create a new account
    def create(self, validated_data):
        new_data = {key: validated_data[key] for key in ["username", "email", "first_name", "last_name"]}
        password = validated_data["password"]

        user_obj = User(**new_data)
        user_obj.set_password(password)
        user_obj.save()

        self.group.user_set.add(user_obj)

        return validated_data


# Serializer for User Config
class UserConfigSerializer(serializers.ModelSerializer):
    default_settings = serializers.DictField(default=models.UserConfig.SETTINGS)

    class Meta:
        model = models.UserConfig
        fields = ("default_settings", ) + tuple(platform + setting for setting in models.UserConfig.SETTINGS for platform in ["desktop_", "mobile_"])
        extra_kwargs = {field: {"read_only": True} for field in ["default_settings", "platform"]}

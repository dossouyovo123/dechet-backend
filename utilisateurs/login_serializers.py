# serializers.py
from rest_framework import serializers
from django.contrib.auth import authenticate
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken
from .models import CustomUser 


class LoginSerializer(serializers.Serializer):
    id_formatte = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        id_formatte = data.get('id_formatte')
        password = data.get('password')

        if id_formatte and password:
            try:
                user = CustomUser.objects.get(id_formatte=id_formatte)
            except CustomUser.DoesNotExist:
                raise AuthenticationFailed('Identifiant ou mot de passe incorrect')

            if not user.check_password(password):
                raise AuthenticationFailed('Identifiant ou mot de passe incorrect')
        else:
            raise AuthenticationFailed('Les champs identifiant et mot de passe sont requis')

        refresh = RefreshToken.for_user(user)
        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': user
        }
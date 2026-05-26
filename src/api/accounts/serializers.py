# serializers for API
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate

from rest_framework import serializers

from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer
)
from shop_epower.accounts.models import LegalProfile



User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):

    password = serializers.CharField(
        write_only=True,
        min_length=8
    )

    class Meta:
        model = User

        fields = (
            'email',
            'username',
            'password',
        )

    def create(self, validated_data):

        return User.objects.create_user(
            email=validated_data['email'],
            username=validated_data['username'],
            password=validated_data['password'],
        )


class LogoutSerializer(serializers.Serializer):

    refresh = serializers.CharField()

    default_error_messages = {
        'bad_token': 'Token is invalid or expired'
    }

    def validate(self, attrs):

        self.token = attrs['refresh']

        return attrs

    def save(self, **kwargs):

        try:
            token = RefreshToken(self.token)
            token.blacklist()

        except Exception:
            self.fail('bad_token')


class CustomTokenObtainPairSerializer(
    TokenObtainPairSerializer
):

    email = serializers.EmailField()

    password = serializers.CharField(
        write_only=True
    )

    def validate(self, attrs):

        credentials = {
            'email': attrs.get('email'),
            'password': attrs.get('password')
        }

        user = authenticate(**credentials)

        if user is None:
            raise serializers.ValidationError(
                'Invalid credentials'
            )

        refresh = self.get_token(user)

        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }

class LegalProfileSerializer(serializers.ModelSerializer):

    class Meta:
        model = LegalProfile
        fields = (
            'is_legal_entity',
            'company_name',
            'tax_id',
            'legal_address',
            'bank_name',
            'bank_account',
        )

    def validate(self, attrs):
        is_legal_entity = attrs.get(
            'is_legal_entity',
            getattr(self.instance, 'is_legal_entity', False)
        )

        if is_legal_entity:
            required_fields = (
                'company_name',
                'tax_id',
                'legal_address',
                'bank_name',
                'bank_account',
            )

            for field in required_fields:
                value = attrs.get(
                    field,
                    getattr(self.instance, field, '')
                )

                if not value:
                    raise serializers.ValidationError({
                        field: 'This field is required for legal entity / sole proprietor.'
                    })

        return attrs


class UserProfileSerializer(serializers.ModelSerializer):

    legal_profile = LegalProfileSerializer()

    class Meta:
        model = User
        fields = (
            'email',
            'username',
            'first_name',
            'last_name',
            'phone',
            'legal_profile',
        )

    def update(self, instance, validated_data):
        legal_profile_data = validated_data.pop(
            'legal_profile',
            None
        )

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if legal_profile_data is not None:
            legal_profile, created = LegalProfile.objects.get_or_create(
                user=instance
            )

            for attr, value in legal_profile_data.items():
                setattr(legal_profile, attr, value)

            legal_profile.save()

        return instance

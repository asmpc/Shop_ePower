# DRF
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

# JWT
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

# Swagger
from drf_spectacular.utils import extend_schema

# Local
from .serializers import (
    RegisterSerializer,
    LogoutSerializer,
    UserProfileSerializer,
)
from shop_epower.accounts.models import LegalProfile


@extend_schema(
    tags=["Accounts"],
    summary="User login",
    description="Get access and refresh tokens",
)
class CustomTokenObtainPairView(TokenObtainPairView):
    pass


@extend_schema(
    tags=["Accounts"],
    summary="Refresh access token",
    description="Refresh JWT access token",
)
class CustomTokenRefreshView(TokenRefreshView):
    pass


@extend_schema(
    tags=["Accounts"],
    summary="User registration",
    description="Create new user account",
)
class RegisterAPIView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


@extend_schema(
    tags=["Accounts"],
    summary="Logout user",
    description="Blacklist refresh token",
)
class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(status=status.HTTP_205_RESET_CONTENT)

@extend_schema(
    tags=["Accounts"],
    summary="User profile",
    description="Get or update current user profile",
)
class UserProfileAPIView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        LegalProfile.objects.get_or_create(
            user=self.request.user
        )

        return self.request.user
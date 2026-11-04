# DRF
# Swagger
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

# JWT
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

# Local
from api.accounts.serializers import (
    CustomerAccountBalanceSerializer,
    LogoutSerializer,
    RegisterSerializer,
    UserProfileSerializer,
)
from shop_epower.accounts.models import LegalProfile
from shop_epower.finance.selectors import get_customer_account_balances


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


@extend_schema(
    tags=["Accounts"],
    summary="Current user account balances",
    description="Return financial balances of the authenticated user's accounts.",
)
class CustomerAccountBalanceListAPIView(generics.ListAPIView):
    serializer_class = CustomerAccountBalanceSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return get_customer_account_balances(
            user=self.request.user,
        )
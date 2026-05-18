# Django
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    TemplateView,
)

from django.contrib.auth.views import (
    LoginView,
    LogoutView,
)

from django.contrib.auth.mixins import (
    LoginRequiredMixin,
)

# DRF
from rest_framework import (
    generics,
    status,
)

from rest_framework.response import Response

from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
)

from rest_framework.views import APIView

# JWT
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

# Swagger
from drf_spectacular.utils import extend_schema

# Local
from .forms import (
    LoginForm,
    RegisterForm,
)

from .serializers import (
    RegisterSerializer,
    LogoutSerializer,
)



@extend_schema(
    tags=['Accounts'],
    summary='User login',
    description='Get access and refresh tokens',
)
class CustomTokenObtainPairView(TokenObtainPairView):
    pass


@extend_schema(
    tags=['Accounts'],
    summary='Refresh access token',
    description='Refresh JWT access token',
)
class CustomTokenRefreshView(TokenRefreshView):
    pass


@extend_schema(
    tags=['Accounts'],
    summary='User registration',
    description='Create new user account',
)
class RegisterView(generics.CreateAPIView):

    serializer_class = RegisterSerializer

    permission_classes = [AllowAny]


@extend_schema(
    tags=['Accounts'],
    summary='Logout user',
    description='Blacklist refresh token',
)
class LogoutAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        serializer = LogoutSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        serializer.save()

        return Response(
            status=status.HTTP_205_RESET_CONTENT
        )


class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'

    authentication_form = LoginForm

    redirect_authenticated_user = True

    next_page = reverse_lazy('profile')


class CustomLogoutView(LogoutView):

    next_page = reverse_lazy('home')


class RegisterTemplateView(CreateView):

    form_class = RegisterForm

    template_name = 'accounts/register.html'

    success_url = reverse_lazy('login-template')


class ProfileView(
    LoginRequiredMixin,
    TemplateView
):
    template_name = 'accounts/profile.html'

    login_url = 'login-template'
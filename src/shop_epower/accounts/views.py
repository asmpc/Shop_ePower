# Django
from django.urls import reverse_lazy, reverse
from django.views.generic import CreateView, TemplateView

from django.contrib.auth.views import (
    LoginView,
    LogoutView,
)

from django.contrib.auth.mixins import LoginRequiredMixin

# Local
from .forms import (
    LoginForm,
    RegisterForm,
)


class CustomLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        next_url = self.get_redirect_url()

        if next_url:
            return next_url

        return reverse("catalog:product_list")


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy("home")


class RegisterTemplateView(CreateView):
    form_class = RegisterForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("login-template")


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/profile.html"
    login_url = "login-template"
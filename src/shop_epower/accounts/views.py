# Django
from django.urls import reverse_lazy, reverse
from django.views.generic import CreateView, TemplateView

from django.contrib.auth.views import (
    LoginView,
    LogoutView,
)

from django.contrib.auth.mixins import LoginRequiredMixin

from django.contrib import messages

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

# Local
from .forms import (
    LoginForm,
    RegisterForm,
    LegalProfileForm,
    UserProfileForm,
)

from shop_epower.cart.services import merge_session_cart_to_user_cart

from .models import LegalProfile



class CustomLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        old_session_key = self.request.session.session_key

        response = super().form_valid(form)

        cart_updated = merge_session_cart_to_user_cart(
            self.request,
            self.request.user,
            old_session_key=old_session_key,
        )

        if cart_updated:
            messages.success(
                self.request,
                "Cart updated with your account prices."
            )

        return response

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
    success_url = reverse_lazy("accounts:login")


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/profile.html"
    login_url = 'accounts:login'


@login_required
def profile_edit(request):

    legal_profile, created = LegalProfile.objects.get_or_create(
        user=request.user,
    )

    if request.method == 'POST':
        user_form = UserProfileForm(
            request.POST,
            instance=request.user,
        )

        legal_profile_form = LegalProfileForm(
            request.POST,
            instance=legal_profile,
        )

        if user_form.is_valid() and legal_profile_form.is_valid():
            user_form.save()

            legal_profile = legal_profile_form.save(commit=False)

            if not legal_profile.is_legal_entity:
                old = LegalProfile.objects.get(user=request.user)

                legal_profile.company_name = old.company_name
                legal_profile.tax_id = old.tax_id
                legal_profile.legal_address = old.legal_address
                legal_profile.bank_name = old.bank_name
                legal_profile.bank_account = old.bank_account

            legal_profile.save()

            messages.success(request, 'Profile updated successfully.')

            return redirect('accounts:profile_edit')

    else:
        user_form = UserProfileForm(
            instance=request.user,
        )

        legal_profile_form = LegalProfileForm(
            instance=legal_profile,
        )

    return render(
        request,
        'accounts/profile_edit.html',
        {
            'user_form': user_form,
            'legal_profile_form': legal_profile_form,
        }
    )
from django.urls import reverse_lazy, reverse
from django.views.generic import CreateView, TemplateView

from django.contrib.auth.views import (
    LoginView,
    LogoutView,
)

from urllib.parse import urlencode

from django.contrib.auth.mixins import LoginRequiredMixin

from django.contrib import messages

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required

from django.shortcuts import redirect, render

from .forms import (
    LoginForm,
    RegisterForm,
    LegalProfileForm,
    UserProfileForm,
)

from shop_epower.cart.services import merge_session_cart_to_user_cart

from .models import LegalProfile

from django.utils.http import url_has_allowed_host_and_scheme



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

    def form_valid(self, form):
        response = super().form_valid(form)

        login(
            self.request,
            self.object,
        )

        return response

    def get_success_url(self):
        profile_edit_url = reverse(
            "accounts:profile_edit",
        )

        next_url = self.request.GET.get(
            "next",
        )

        if next_url and url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts={self.request.get_host()},
                require_https=self.request.is_secure(),
        ):
            query_string = urlencode(
                {
                    "next": next_url,
                }
            )

            return (
                f"{profile_edit_url}"
                f"?{query_string}"
            )

        return profile_edit_url


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

            next_url = request.GET.get('next')

            if next_url and url_has_allowed_host_and_scheme(
                    url=next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
            ):
                return redirect(next_url)

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
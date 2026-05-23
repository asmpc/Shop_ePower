# Forms for accounts

from django import forms

from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm,
)

from django.contrib.auth import get_user_model


User = get_user_model()

class LoginForm(AuthenticationForm):

    username = forms.EmailField(
        label='Email'
    )


class RegisterForm(UserCreationForm):

    class Meta:

        model = User

        fields = (
            'email',
            'username',
            'password1',
            'password2',
        )
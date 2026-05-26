# Forms for accounts

from django import forms

from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm,
)

from .models import LegalProfile, User

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



class UserProfileForm(forms.ModelForm):

    class Meta:
        model = User
        fields = (
            'username',
            'first_name',
            'last_name',
            'email',
            'phone',
        )

        widgets = {
            'username': forms.TextInput(
                attrs={'class': 'form-control'}
            ),
            'first_name': forms.TextInput(
                attrs={'class': 'form-control'}
            ),
            'last_name': forms.TextInput(
                attrs={'class': 'form-control'}
            ),
            'email': forms.EmailInput(
                attrs={'class': 'form-control'}
            ),
            'phone': forms.TextInput(
                attrs={'class': 'form-control'}
            ),
        }


class LegalProfileForm(forms.ModelForm):

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

        widgets = {
            'is_legal_entity': forms.CheckboxInput(
                attrs={'class': 'form-check-input'}
            ),
            'company_name': forms.TextInput(
                attrs={'class': 'form-control'}
            ),
            'tax_id': forms.TextInput(
                attrs={'class': 'form-control'}
            ),
            'legal_address': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 3,
                }
            ),
            'bank_name': forms.TextInput(
                attrs={'class': 'form-control'}
            ),
            'bank_account': forms.TextInput(
                attrs={'class': 'form-control'}
            ),
        }

    def clean(self):
        cleaned_data = super().clean()

        is_legal_entity = cleaned_data.get('is_legal_entity')

        if is_legal_entity:
            required_fields = (
                'company_name',
                'tax_id',
                'legal_address',
                'bank_name',
                'bank_account',
            )

            for field in required_fields:
                if not cleaned_data.get(field):
                    self.add_error(
                        field,
                        'This field is required for legal entity / sole proprietor.'
                    )

        return cleaned_data
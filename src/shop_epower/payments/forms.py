from decimal import Decimal

from django import forms

from shop_epower.payments.choices import PaymentMethod
from shop_epower.payments.models import PayoutMethod


class ManualPaymentReceiptForm(forms.Form):
    amount = forms.DecimalField(
        label="Amount received",
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "step": "0.01",
                "min": "0.01",
            },
        ),
    )
    method = forms.ChoiceField(
        label="Receipt method",
        choices=[
            (PaymentMethod.ON_RECEIPT, "Office payment"),
            (PaymentMethod.INVOICE, "Bank transfer"),
        ],
        widget=forms.Select(
            attrs={"class": "form-select"},
        ),
    )
    comment = forms.CharField(
        label="Manager comment",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
            },
        ),
    )
    operation_key = forms.CharField(
        max_length=255,
        widget=forms.HiddenInput(),
    )


class ManualReceiptCancellationForm(forms.Form):
    comment = forms.CharField(
        label="Cancellation reason",
        required=True,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
            },
        ),
    )
    operation_key = forms.CharField(
        max_length=255,
        widget=forms.HiddenInput(),
    )


class ManualAccountPayoutForm(forms.Form):
    amount = forms.DecimalField(
        label="Amount to return",
        max_digits=18,
        decimal_places=2,
        min_value=Decimal("0.01"),
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "step": "0.01",
                "min": "0.01",
            },
        ),
    )

    method = forms.ChoiceField(
        label="Payout method",
        choices=PayoutMethod.choices,
        widget=forms.Select(
            attrs={"class": "form-select"},
        ),
    )

    comment = forms.CharField(
        label="Payout reason",
        required=True,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
            },
        ),
    )

    operation_key = forms.CharField(
        max_length=255,
        widget=forms.HiddenInput(),
    )

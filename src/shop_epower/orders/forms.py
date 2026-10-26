from decimal import Decimal

from django import forms


class OrderFundAssignmentForm(forms.Form):
    amount = forms.DecimalField(
        label="Amount to assign",
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


class OrderFundAssignmentCancelForm(forms.Form):
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
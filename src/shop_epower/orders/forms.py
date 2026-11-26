from decimal import Decimal

from django import forms
from django.core.validators import MaxValueValidator

from shop_epower.catalog.models import Product


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


class OrderItemQuantityReductionForm(forms.Form):
    new_quantity = forms.IntegerField(
        label="New quantity",
        min_value=1,
        required=True,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "step": "1",
            },
        ),
    )
    reason = forms.CharField(
        label="Reason for change",
        required=True,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
            },
        ),
    )

    def __init__(self, *args, order_item, **kwargs):
        super().__init__(*args, **kwargs)

        maximum = order_item.quantity - 1
        quantity_field = self.fields["new_quantity"]

        quantity_field.max_value = maximum
        quantity_field.validators.append(
            MaxValueValidator(maximum),
        )
        quantity_field.widget.attrs["max"] = maximum


class OrderItemRemovalForm(forms.Form):
    reason = forms.CharField(
        label="Reason for removal",
        required=True,
        help_text="Visible to staff only.",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
            },
        ),
    )


class OrderItemAdditionForm(forms.Form):
    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(is_active=True),
        widget=forms.HiddenInput(),
    )
    quantity = forms.IntegerField(
        label="Quantity",
        min_value=1,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "step": "1",
            },
        ),
    )
    confirmed_unit_price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        widget=forms.HiddenInput(),
    )


class OrderItemsAdditionReasonForm(forms.Form):
    reason = forms.CharField(
        label="Reason for addition",
        required=True,
        help_text="Visible to staff only.",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
            },
        ),
    )


OrderItemAdditionFormSet = forms.formset_factory(
    OrderItemAdditionForm,
    extra=0,
    can_delete=True,
)
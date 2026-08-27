from django import forms

from shop_epower.orders.models import Order


class ChatRoomCreateForm(forms.Form):
    order = forms.ModelChoiceField(
        queryset=Order.objects.none(),
        required=False,
        empty_label="General question",
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        if user is not None:
            self.fields["order"].queryset = Order.objects.filter(
                user=user,
            )

class ChatMessageForm(forms.Form):
    text = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 4,
            }
        )
    )

    files = forms.FileField(
        required=False,
    )
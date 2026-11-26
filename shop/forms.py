from django import forms


class PurchaseForm(forms.Form):
    address = forms.CharField(
        label='Адрес доставки', max_length=200,
        widget=forms.TextInput(attrs={'autocomplete': 'street-address'}),
    )
    checkout_id = forms.UUIDField(widget=forms.HiddenInput)

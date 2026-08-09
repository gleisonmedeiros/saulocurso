from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, SetPasswordForm

INPUT_CLASS = "w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-600"


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASS


class TrocarSenhaForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASS


class EsqueciSenhaForm(forms.Form):
    email = forms.EmailField(
        label="Seu email cadastrado",
        widget=forms.EmailInput(attrs={"class": INPUT_CLASS, "placeholder": "voce@email.com", "autofocus": True}),
    )


class CodigoForm(forms.Form):
    codigo = forms.CharField(
        label="Código recebido por email", max_length=6,
        widget=forms.TextInput(attrs={
            "class": INPUT_CLASS + " tracking-widest text-center text-lg",
            "placeholder": "000000", "inputmode": "numeric", "autocomplete": "one-time-code", "autofocus": True,
        }),
    )

    def clean_codigo(self):
        return self.cleaned_data["codigo"].strip()


class NovaSenhaForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASS

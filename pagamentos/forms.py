import re

from django import forms
from django.contrib.auth.models import User

INPUT_CLASS = "w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-600"


class CadastroPosPagamentoForm(forms.Form):
    nome = forms.CharField(label="Nome completo", max_length=150)
    cpf = forms.CharField(label="CPF", max_length=14)
    telefone = forms.CharField(label="Telefone (WhatsApp)", max_length=20)
    email = forms.EmailField(label="Email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASS

    def clean_cpf(self):
        cpf = re.sub(r"\D", "", self.cleaned_data["cpf"])
        if len(cpf) != 11:
            raise forms.ValidationError("CPF inválido — deve ter 11 dígitos.")
        return cpf

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError("Já existe uma conta com este email. Faça login pra continuar.")
        return email

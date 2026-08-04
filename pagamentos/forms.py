import re

from django import forms

from .models import Pagamento

INPUT_CLASS = "w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-600"


class CadastroAlunoForm(forms.Form):
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
        # Só bloqueia se já tiver uma compra de verdade nesse email — uma
        # tentativa anterior que não chegou a pagar (conta "pendente", senha
        # inutilizável) não deve travar uma nova tentativa.
        if Pagamento.objects.filter(aluno__username__iexact=email, status="aprovado").exists():
            raise forms.ValidationError("Já existe uma conta com este email. Faça login pra continuar.")
        return email

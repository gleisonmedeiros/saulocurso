from django import forms

INPUT_CLASS = "w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-600"


class ContatoForm(forms.Form):
    email = forms.EmailField(label="Email")
    telefone = forms.CharField(label="Telefone (opcional)", max_length=20, required=False)
    mensagem = forms.CharField(label="Mensagem", widget=forms.Textarea(attrs={"rows": 5}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASS

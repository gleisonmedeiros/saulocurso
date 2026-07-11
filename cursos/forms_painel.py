import re

from django import forms

from .models import Aula, ConfiguracaoSite, Curso, MentoriaAoVivo, Modulo

INPUT_CLASS = "w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-600"
CHECKBOX_CLASS = "h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-600"


def extrair_drive_id(valor):
    """Aceita ID puro ou link de compartilhamento do Drive e devolve só o ID."""
    valor = valor.strip()
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", valor) or re.search(r"[?&]id=([a-zA-Z0-9_-]+)", valor)
    return match.group(1) if match else valor


def _aplicar_classes(form):
    for field in form.fields.values():
        if isinstance(field.widget, forms.CheckboxInput):
            field.widget.attrs["class"] = CHECKBOX_CLASS
        else:
            field.widget.attrs["class"] = INPUT_CLASS
    return form


class CursoForm(forms.ModelForm):
    class Meta:
        model = Curso
        fields = ["titulo", "slug", "descricao_curta", "descricao", "preco", "imagem_capa", "video_youtube_id", "ativo"]
        widgets = {"descricao": forms.Textarea(attrs={"rows": 6})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _aplicar_classes(self)


class ModuloForm(forms.ModelForm):
    class Meta:
        model = Modulo
        fields = ["titulo", "ordem"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _aplicar_classes(self)


class AulaForm(forms.ModelForm):
    class Meta:
        model = Aula
        fields = ["titulo", "youtube_id", "drive_file_id", "arquivo_pdf", "drive_pdf_file_id", "ordem"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["drive_file_id"].help_text = "Cola o ID ou o link de compartilhamento inteiro — o ID é extraído sozinho."
        self.fields["drive_pdf_file_id"].help_text = "Cola o ID ou o link de compartilhamento inteiro — o ID é extraído sozinho."
        _aplicar_classes(self)

    def clean_drive_file_id(self):
        valor = self.cleaned_data.get("drive_file_id", "")
        return extrair_drive_id(valor) if valor else valor

    def clean_drive_pdf_file_id(self):
        valor = self.cleaned_data.get("drive_pdf_file_id", "")
        return extrair_drive_id(valor) if valor else valor


class ConfiguracaoSiteForm(forms.ModelForm):
    class Meta:
        model = ConfiguracaoSite
        fields = [
            "hero_titulo", "hero_subtitulo", "hero_video_youtube_id", "hero_video_drive_file_id",
            "sobre_texto",
            "contato_email", "contato_telefone", "whatsapp_numero",
        ]
        widgets = {
            "hero_subtitulo": forms.Textarea(attrs={"rows": 3}),
            "sobre_texto": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["hero_video_drive_file_id"].help_text = "Cola o ID ou o link de compartilhamento inteiro — o ID é extraído sozinho."
        _aplicar_classes(self)

    def clean_hero_video_drive_file_id(self):
        valor = self.cleaned_data.get("hero_video_drive_file_id", "")
        return extrair_drive_id(valor) if valor else valor


class MentoriaForm(forms.ModelForm):
    class Meta:
        model = MentoriaAoVivo
        fields = ["titulo", "descricao", "data_hora", "link_reuniao"]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 3}),
            "data_hora": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _aplicar_classes(self)
        self.fields["data_hora"].input_formats = ["%Y-%m-%dT%H:%M"]

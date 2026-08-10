import re

from django import forms

from notificacoes.models import ConfiguracaoNotificacao
from pagamentos.models import ConfiguracaoPagamento

from .models import Aula, ConfiguracaoSite, Curso, MentoriaAoVivo, Modulo, PerguntaFrequente, Turma

INPUT_CLASS = "w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-600"
CHECKBOX_CLASS = "h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-600"


class MatricularAlunoForm(forms.Form):
    nome = forms.CharField(label="Nome completo", max_length=150)
    email = forms.EmailField(label="Email (será o login)")
    telefone = forms.CharField(label="Telefone (WhatsApp)", max_length=20, required=False)
    cpf = forms.CharField(label="CPF", max_length=14, required=False)
    cursos = forms.ModelMultipleChoiceField(
        label="Cursos", queryset=Curso.objects.filter(ativo=True).order_by("titulo"),
        widget=forms.CheckboxSelectMultiple, required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "cursos":
                continue
            field.widget.attrs["class"] = INPUT_CLASS

    def clean_cpf(self):
        cpf = re.sub(r"\D", "", self.cleaned_data.get("cpf", ""))
        if cpf and len(cpf) != 11:
            raise forms.ValidationError("CPF inválido — deve ter 11 dígitos.")
        return cpf


def extrair_drive_id(valor):
    """Aceita ID puro ou link de compartilhamento do Drive e devolve só o ID."""
    valor = valor.strip()
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", valor) or re.search(r"[?&]id=([a-zA-Z0-9_-]+)", valor)
    return match.group(1) if match else valor


def extrair_youtube_id(valor):
    """Aceita ID puro ou link do YouTube (watch/youtu.be/embed/shorts) e devolve só o ID."""
    valor = valor.strip()
    match = re.search(
        r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|embed/|shorts/|live/))([a-zA-Z0-9_-]{11})", valor
    )
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
        fields = [
            "titulo", "slug", "descricao_curta", "descricao", "preco",
            "carga_horaria", "modalidade",
            "drive_capa_file_id", "capa_upload", "capa_url_externa", "video_youtube_id", "ativo",
        ]
        widgets = {"descricao": forms.Textarea(attrs={"rows": 6})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["drive_capa_file_id"].help_text = "Cola o ID ou o link de compartilhamento inteiro — o ID é extraído sozinho."
        self.fields["video_youtube_id"].help_text = "Cola o ID ou o link do vídeo inteiro — o ID é extraído sozinho."
        _aplicar_classes(self)

    def clean_drive_capa_file_id(self):
        valor = self.cleaned_data.get("drive_capa_file_id", "")
        return extrair_drive_id(valor) if valor else valor

    def clean_video_youtube_id(self):
        valor = self.cleaned_data.get("video_youtube_id", "")
        return extrair_youtube_id(valor) if valor else valor


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
        fields = ["titulo", "youtube_id", "drive_file_id", "drive_pdf_file_id", "ordem"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["youtube_id"].help_text = "Cola o ID ou o link do vídeo inteiro — o ID é extraído sozinho."
        self.fields["drive_file_id"].help_text = "Cola o ID ou o link de compartilhamento inteiro — o ID é extraído sozinho."
        self.fields["drive_pdf_file_id"].help_text = "Cola o ID ou o link de compartilhamento inteiro — o ID é extraído sozinho."
        _aplicar_classes(self)

    def clean_youtube_id(self):
        valor = self.cleaned_data.get("youtube_id", "")
        return extrair_youtube_id(valor) if valor else valor

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
            "cnpj", "endereco", "instagram_url",
        ]
        widgets = {
            "hero_subtitulo": forms.Textarea(attrs={"rows": 3}),
            "sobre_texto": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["hero_video_youtube_id"].help_text = "Cola o ID ou o link do vídeo inteiro — o ID é extraído sozinho."
        self.fields["hero_video_drive_file_id"].help_text = "Cola o ID ou o link de compartilhamento inteiro — o ID é extraído sozinho."
        _aplicar_classes(self)

    def clean_hero_video_youtube_id(self):
        valor = self.cleaned_data.get("hero_video_youtube_id", "")
        return extrair_youtube_id(valor) if valor else valor

    def clean_hero_video_drive_file_id(self):
        valor = self.cleaned_data.get("hero_video_drive_file_id", "")
        return extrair_drive_id(valor) if valor else valor


class ConfiguracaoPagamentoForm(forms.ModelForm):
    class Meta:
        model = ConfiguracaoPagamento
        fields = ["gateway", "infinitepay_handle"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["infinitepay_handle"].widget.attrs["placeholder"] = "gleison-pereira-z9a"
        _aplicar_classes(self)

    def clean_infinitepay_handle(self):
        valor = self.cleaned_data.get("infinitepay_handle", "").strip().lstrip("$")
        return valor

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("gateway") == ConfiguracaoPagamento.Gateway.INFINITEPAY and not cleaned.get("infinitepay_handle"):
            self.add_error("infinitepay_handle", "Preenche o InfiniteTag pra usar o InfinitePay.")
        return cleaned


class ConfiguracaoNotificacaoForm(forms.ModelForm):
    class Meta:
        model = ConfiguracaoNotificacao
        fields = ["backend", "site_url", "email_host", "email_port", "email_use_tls", "email_host_user", "email_host_password"]
        widgets = {
            "email_host_password": forms.PasswordInput(render_value=True),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _aplicar_classes(self)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("backend") == ConfiguracaoNotificacao.Backend.SMTP:
            if not cleaned.get("email_host_user"):
                self.add_error("email_host_user", "Preenche o email remetente pra usar SMTP real.")
            if not cleaned.get("email_host_password"):
                self.add_error("email_host_password", "Preenche a senha de app pra usar SMTP real.")
        return cleaned


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


class TurmaForm(forms.ModelForm):
    class Meta:
        model = Turma
        fields = ["data_inicio", "local_ou_modalidade", "vagas", "observacao"]
        widgets = {
            "data_inicio": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _aplicar_classes(self)
        self.fields["data_inicio"].input_formats = ["%Y-%m-%dT%H:%M"]


class PerguntaFrequenteForm(forms.ModelForm):
    class Meta:
        model = PerguntaFrequente
        fields = ["pergunta", "resposta", "ordem", "ativa"]
        widgets = {"resposta": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _aplicar_classes(self)

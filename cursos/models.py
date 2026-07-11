from django.db import models
from django.urls import reverse


class Curso(models.Model):
    titulo = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    descricao_curta = models.CharField("descrição curta (propaganda)", max_length=300)
    descricao = models.TextField("descrição completa")
    preco = models.DecimalField(max_digits=8, decimal_places=2)
    imagem_capa = models.ImageField(upload_to="cursos/capas/", blank=True, null=True)
    video_youtube_id = models.CharField("ID do vídeo de apresentação (YouTube)", max_length=20, blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return self.titulo

    def get_absolute_url(self):
        return reverse("cursos:detalhe", args=[self.slug])


class Modulo(models.Model):
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name="modulos")
    titulo = models.CharField(max_length=200)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordem", "id"]

    def __str__(self):
        return f"{self.curso.titulo} — {self.titulo}"


class Aula(models.Model):
    modulo = models.ForeignKey(Modulo, on_delete=models.CASCADE, related_name="aulas")
    titulo = models.CharField(max_length=200)
    youtube_id = models.CharField("ID do vídeo no YouTube", max_length=20, blank=True)
    drive_file_id = models.CharField(
        "ID do arquivo no Google Drive",
        max_length=100,
        blank=True,
        help_text="Preenchendo este campo, o vídeo é servido pelo Google Drive em vez do YouTube "
        "(sem marca/link do YouTube). Pegue o ID na URL de compartilhamento: "
        "drive.google.com/file/d/ESSE-TRECHO-AQUI/view — e desative a opção de download "
        "pra quem visualiza, nas configurações de compartilhamento do arquivo.",
    )
    arquivo_pdf = models.FileField("apostila em PDF (upload local)", upload_to="cursos/apostilas/", blank=True, null=True)
    drive_pdf_file_id = models.CharField(
        "ID da apostila no Google Drive",
        max_length=100,
        blank=True,
        help_text="Alternativa ao upload local — preenchendo este campo, a apostila é servida "
        "direto do Google Drive (útil em hospedagem sem disco persistente, tipo Vercel). "
        "Mesmo esquema do vídeo: pega o ID em drive.google.com/file/d/ESSE-TRECHO-AQUI/view "
        "e desativa a opção de download pra quem visualiza.",
    )
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordem", "id"]

    def __str__(self):
        return f"{self.modulo.titulo} — {self.titulo}"

    @property
    def curso(self):
        return self.modulo.curso


class MentoriaAoVivo(models.Model):
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name="mentorias")
    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    data_hora = models.DateTimeField()
    link_reuniao = models.URLField("link da reunião (Meet/Zoom)", blank=True)

    class Meta:
        ordering = ["data_hora"]

    def __str__(self):
        return f"{self.titulo} ({self.data_hora:%d/%m/%Y %H:%M})"


class ConfiguracaoSite(models.Model):
    """Textos e contatos editáveis da tela inicial. Existe no máximo 1 linha (singleton)."""

    hero_titulo = models.CharField(max_length=200, default="Transforme sua carreira com nossos cursos")
    hero_subtitulo = models.TextField(
        default="Aulas em vídeo, apostilas em PDF e mentoria ao vivo. Acesso liberado na hora, "
        "direto no navegador — no computador ou no celular."
    )
    hero_video_youtube_id = models.CharField("ID do vídeo de apresentação (YouTube)", max_length=20, blank=True, default="S9uPNppGsGo")
    hero_video_drive_file_id = models.CharField(
        "ID do vídeo de apresentação (Google Drive)",
        max_length=100,
        blank=True,
        help_text="Alternativa ao YouTube — preenchendo este campo, o vídeo do hero é servido pelo "
        "Google Drive (tem prioridade sobre o YouTube). Cola o ID ou o link inteiro, extrai sozinho.",
    )

    sobre_texto = models.TextField(
        default="Somos uma plataforma de ensino online focada em resultado prático. Cada curso combina "
        "videoaulas, material de apoio em PDF e encontros de mentoria ao vivo com o instrutor."
    )

    contato_email = models.EmailField(default="contato@saulocurso.local")
    contato_telefone = models.CharField(max_length=20, default="(11) 90000-0000")
    whatsapp_numero = models.CharField(
        "Número do WhatsApp",
        max_length=20,
        default="5522998051490",
        help_text="Só números, com código do país e DDD (ex: 5522998051490).",
    )

    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração do site"
        verbose_name_plural = "Configurações do site"

    def __str__(self):
        return "Configurações do site"

    @classmethod
    def obter(cls):
        config, _ = cls.objects.get_or_create(pk=1)
        return config


class ContatoMensagem(models.Model):
    email = models.EmailField()
    telefone = models.CharField(max_length=20, blank=True)
    mensagem = models.TextField()
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-enviado_em"]
        verbose_name = "Mensagem de contato"
        verbose_name_plural = "Mensagens de contato"

    def __str__(self):
        return f"{self.email} — {self.enviado_em:%d/%m/%Y %H:%M}"

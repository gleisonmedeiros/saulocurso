from django.db import models


class ConfiguracaoNotificacao(models.Model):
    """Qual backend de notificação tá ativo (mock ou SMTP de verdade) e as
    credenciais SMTP — editável pelo painel, sem precisar de env var/redeploy.
    Singleton (pk=1 via .obter()), mesmo padrão do ConfiguracaoPagamento."""

    class Backend(models.TextChoices):
        MOCK = "mock", "Modo teste (só registra, não envia nada de verdade)"
        SMTP = "smtp", "Email real (SMTP — Gmail/Google Workspace)"

    backend = models.CharField(max_length=20, choices=Backend.choices, default=Backend.MOCK)
    site_url = models.URLField(
        "URL do site (Portal do Aluno)", default="https://rscentraldoscursos.com.br",
        help_text="Endereço base usado nos links dos emails enviados ao aluno. "
        "Ex.: https://rscentraldoscursos.com.br (sem barra no fim).",
    )
    email_host = models.CharField("servidor SMTP", max_length=255, blank=True, default="smtp.gmail.com")
    email_port = models.PositiveIntegerField("porta SMTP", default=587)
    email_use_tls = models.BooleanField("usar TLS", default=True)
    email_host_user = models.EmailField(
        "email remetente", blank=True, help_text="A conta Gmail/Google Workspace que vai enviar.",
    )
    email_host_password = models.CharField(
        "senha de app", max_length=255, blank=True,
        help_text="Senha de app do Google (16 caracteres) — não é a senha normal da conta. "
        "Gera em myaccount.google.com/apppasswords (precisa de verificação em 2 etapas ativada).",
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração de notificações"
        verbose_name_plural = "Configuração de notificações"

    def __str__(self):
        return "Configuração de notificações"

    @classmethod
    def obter(cls):
        config, _ = cls.objects.get_or_create(pk=1)
        return config

    def email_destino_admin(self):
        """Pra onde vão os avisos de matrícula/contato: o email remetente
        configurado no painel; se vazio, o default do settings."""
        from django.conf import settings
        return self.email_host_user or settings.ADMIN_NOTIFICATION_EMAIL


class ModeloEmail(models.Model):
    """Texto (assunto + corpo) de um email, editável no painel. Se assunto ou
    corpo ficarem em branco, o service usa o padrão de notificacoes.emails."""

    chave = models.CharField(max_length=50, unique=True)
    assunto = models.CharField(max_length=255, blank=True)
    corpo = models.TextField(blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Modelo de email"
        verbose_name_plural = "Modelos de email"

    def __str__(self):
        from .emails import MODELOS
        return MODELOS.get(self.chave, {}).get("nome", self.chave)

    @classmethod
    def texto(cls, chave):
        """Retorna (assunto, corpo) efetivos: o que estiver salvo no painel ou,
        se vazio, o padrão embutido em emails.MODELOS."""
        from .emails import MODELOS
        base = MODELOS[chave]
        row = cls.objects.filter(chave=chave).first()
        assunto = (row.assunto if row and row.assunto.strip() else base["assunto"])
        corpo = (row.corpo if row and row.corpo.strip() else base["corpo"])
        return assunto, corpo


class NotificacaoLog(models.Model):
    CANAL_CHOICES = [
        ("email", "Email"),
        ("whatsapp", "WhatsApp"),
    ]

    canal = models.CharField(max_length=10, choices=CANAL_CHOICES)
    destinatario = models.CharField(max_length=200)
    assunto = models.CharField(max_length=200, blank=True)
    mensagem = models.TextField()
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-enviado_em"]
        verbose_name = "Notificação enviada"
        verbose_name_plural = "Notificações enviadas"

    def __str__(self):
        return f"[{self.canal}] {self.destinatario} — {self.enviado_em:%d/%m/%Y %H:%M}"

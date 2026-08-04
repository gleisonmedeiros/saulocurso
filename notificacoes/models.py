from django.db import models


class ConfiguracaoNotificacao(models.Model):
    """Qual backend de notificação tá ativo (mock ou SMTP de verdade) e as
    credenciais SMTP — editável pelo painel, sem precisar de env var/redeploy.
    Singleton (pk=1 via .obter()), mesmo padrão do ConfiguracaoPagamento."""

    class Backend(models.TextChoices):
        MOCK = "mock", "Modo teste (só registra, não envia nada de verdade)"
        SMTP = "smtp", "Email real (SMTP — Gmail/Google Workspace)"

    backend = models.CharField(max_length=20, choices=Backend.choices, default=Backend.MOCK)
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

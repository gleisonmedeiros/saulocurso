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

    # --- WhatsApp (Z-API) ---
    class WhatsAppBackend(models.TextChoices):
        MOCK = "mock", "Modo teste (não envia WhatsApp de verdade)"
        ZAPI = "zapi", "WhatsApp real (Z-API)"

    whatsapp_backend = models.CharField(
        "envio de WhatsApp", max_length=20, choices=WhatsAppBackend.choices, default=WhatsAppBackend.MOCK,
    )
    zapi_instance_id = models.CharField(
        "ID da instância", max_length=100, blank=True,
        help_text="No painel Z-API: 'ID da instância'. Ex.: 3F7BA3E0486D6127AD3ED27B159993B4",
    )
    zapi_token = models.CharField(
        "Token da instância", max_length=200, blank=True,
        help_text="No painel Z-API: 'Token da instância'. Ex.: A9AECD6E973E3C1F38BDCBD9",
    )
    zapi_client_token = models.CharField(
        "Client-Token (Account Security Token)", max_length=200, blank=True,
        help_text="No painel Z-API, menu Segurança → 'Account Security Token'. "
        "É diferente do token da instância. Se não ativou a segurança, deixe vazio.",
    )
    whatsapp_admin = models.CharField(
        "WhatsApp do admin", max_length=20, blank=True,
        help_text="Número que recebe os avisos de admin (matrícula, contato). Com DDD, ex.: 11998887777.",
    )

    # Quais notificações também vão por WhatsApp (quando o envio real estiver ligado)
    zap_credenciais = models.BooleanField("WhatsApp: boas-vindas/credenciais", default=False)
    zap_matricula = models.BooleanField("WhatsApp: matrícula confirmada", default=False)
    zap_codigo = models.BooleanField("WhatsApp: código de recuperação", default=False)
    zap_mentoria = models.BooleanField("WhatsApp: aviso de mentoria", default=False)
    zap_ingresso_turma = models.BooleanField("WhatsApp: ingresso em turma", default=False)
    zap_turma_aberta = models.BooleanField("WhatsApp: turma nova (interessados)", default=False)
    zap_contato = models.BooleanField("WhatsApp: contato/orçamento (admin)", default=False)
    zap_comunicado = models.BooleanField("WhatsApp: comunicado em massa (cuidado: risco de bloqueio)", default=False)

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

    def whatsapp_real(self):
        return self.whatsapp_backend == self.WhatsAppBackend.ZAPI

    def zap_habilitado(self, chave):
        """WhatsApp real ligado E o toggle daquela notificação marcado."""
        return self.whatsapp_real() and bool(getattr(self, f"zap_{chave}", False))


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

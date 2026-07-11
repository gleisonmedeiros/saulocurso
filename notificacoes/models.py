from django.db import models


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

from django.conf import settings
from django.db import models
from django.utils import timezone


class Perfil(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil")
    telefone = models.CharField("telefone (WhatsApp)", max_length=20, blank=True)
    cpf = models.CharField("CPF", max_length=14, blank=True)
    deve_trocar_senha = models.BooleanField("precisa trocar a senha no próximo acesso", default=False)

    def __str__(self):
        return f"Perfil de {self.user.get_username()}"


class CodigoRecuperacaoSenha(models.Model):
    """Código de uso único enviado por email pro aluno redefinir a senha
    quando esquece. Guarda só o hash do código, com prazo e limite de
    tentativas — igual senha, nunca em texto puro."""

    MAX_TENTATIVAS = 5

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="codigos_recuperacao")
    codigo_hash = models.CharField(max_length=255)
    criado_em = models.DateTimeField(auto_now_add=True)
    expira_em = models.DateTimeField()
    tentativas = models.PositiveSmallIntegerField(default=0)
    usado = models.BooleanField(default=False)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Código de {self.user.get_username()} ({self.criado_em:%d/%m/%Y %H:%M})"

    def expirado(self):
        return timezone.now() >= self.expira_em

    def valido(self):
        return not self.usado and not self.expirado() and self.tentativas < self.MAX_TENTATIVAS

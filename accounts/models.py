from django.conf import settings
from django.db import models


class Perfil(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil")
    telefone = models.CharField("telefone (WhatsApp)", max_length=20, blank=True)
    cpf = models.CharField("CPF", max_length=14, blank=True)
    deve_trocar_senha = models.BooleanField("precisa trocar a senha no próximo acesso", default=False)

    def __str__(self):
        return f"Perfil de {self.user.get_username()}"

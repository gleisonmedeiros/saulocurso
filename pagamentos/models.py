from django.conf import settings
from django.db import models


class Pagamento(models.Model):
    STATUS_CHOICES = [
        ("pendente", "Pendente"),
        ("aprovado", "Aprovado"),
        ("recusado", "Recusado"),
    ]

    aluno = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pagamentos")
    curso = models.ForeignKey("cursos.Curso", on_delete=models.CASCADE, related_name="pagamentos")
    valor = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pendente")
    metodo = models.CharField(max_length=30, default="mock")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.aluno.get_username()} — {self.curso.titulo} — {self.status}"

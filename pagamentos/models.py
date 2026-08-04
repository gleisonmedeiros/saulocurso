from django.conf import settings
from django.db import models


class ConfiguracaoPagamento(models.Model):
    """Qual gateway de pagamento tá ativo — editável pelo painel, sem precisar
    mexer no .env/redeploy. Singleton (pk=1 via .obter()), mesmo padrão do
    cursos.ConfiguracaoSite."""

    class Gateway(models.TextChoices):
        MOCK = "mock", "Modo teste (pagamento de enfeite, aprova tudo na hora)"
        INFINITEPAY = "infinitepay", "InfinitePay (pagamento real)"

    gateway = models.CharField(max_length=20, choices=Gateway.choices, default=Gateway.MOCK)
    infinitepay_handle = models.CharField(
        "InfiniteTag",
        max_length=100,
        blank=True,
        help_text="Seu identificador no InfinitePay, sem o \"$\" (ex: gleison-pereira-z9a). "
        "Só é usado quando o gateway acima é InfinitePay.",
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração de pagamento"
        verbose_name_plural = "Configuração de pagamento"

    def __str__(self):
        return "Configuração de pagamento"

    @classmethod
    def obter(cls):
        config, _ = cls.objects.get_or_create(pk=1)
        return config


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


class CobrancaExterna(models.Model):
    """Rastreia uma cobrança criada num gateway externo (InfinitePay) até a
    confirmação via webhook. O Pagamento (status='pendente') já é criado no
    checkout — isso só guarda o order_nsu/transaction_nsu pra casar com a
    notificação de confirmação depois."""

    order_nsu = models.CharField("número do pedido", max_length=64, unique=True)
    pagamento = models.OneToOneField(Pagamento, on_delete=models.CASCADE, related_name="cobranca_externa")
    confirmado = models.BooleanField(default=False)
    transaction_nsu = models.CharField(max_length=64, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    confirmado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Cobrança externa"
        verbose_name_plural = "Cobranças externas"

    def __str__(self):
        return f"{self.order_nsu} — {self.pagamento} — {'confirmado' if self.confirmado else 'pendente'}"

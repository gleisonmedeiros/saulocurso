from abc import ABC, abstractmethod
from dataclasses import dataclass

from django.conf import settings


@dataclass
class ResultadoPagamento:
    aprovado: bool
    referencia: str = ""
    motivo_recusa: str = ""


class PaymentGateway(ABC):
    """Interface comum. Implementações reais (Mercado Pago, Stripe) devem seguir o mesmo contrato."""

    @abstractmethod
    def cobrar(self, aluno, curso, valor) -> ResultadoPagamento:
        raise NotImplementedError


class MockPaymentGateway(PaymentGateway):
    """Aprova qualquer cobrança na hora. Usado enquanto não há gateway real integrado."""

    def cobrar(self, aluno, curso, valor) -> ResultadoPagamento:
        return ResultadoPagamento(aprovado=True, referencia="mock-aprovado")


_GATEWAYS = {
    "mock": MockPaymentGateway,
}


def get_payment_gateway() -> PaymentGateway:
    nome = getattr(settings, "PAYMENT_GATEWAY", "mock")
    gateway_cls = _GATEWAYS.get(nome, MockPaymentGateway)
    return gateway_cls()

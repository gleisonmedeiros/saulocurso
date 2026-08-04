import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)


@dataclass
class ResultadoPagamento:
    aprovado: bool
    referencia: str = ""
    motivo_recusa: str = ""


class PaymentGateway(ABC):
    """Interface pra gateways SÍNCRONOS (aprova/recusa na mesma requisição).
    Só serve pro mock. Gateways de verdade tipo InfinitePay funcionam por
    redirecionamento + webhook assíncrono — não cabem nesse contrato, por
    isso não tentam implementar essa classe (ver InfinitePayGateway abaixo,
    com métodos próprios, usada direto pela view quando o gateway é esse)."""

    @abstractmethod
    def cobrar(self, aluno, curso, valor) -> ResultadoPagamento:
        raise NotImplementedError


class MockPaymentGateway(PaymentGateway):
    """Aprova qualquer cobrança na hora. Usado enquanto não há gateway real integrado."""

    def cobrar(self, aluno, curso, valor) -> ResultadoPagamento:
        return ResultadoPagamento(aprovado=True, referencia="mock-aprovado")


def get_payment_gateway() -> PaymentGateway:
    return MockPaymentGateway()


INFINITEPAY_LINKS_URL = "https://api.checkout.infinitepay.io/links"
INFINITEPAY_CHECK_URL = "https://api.checkout.infinitepay.io/payment_check"


class InfinitePayGateway:
    """Checkout integrado InfinitePay (https://ajuda.infinitepay.io) — link de
    pagamento hospedado + confirmação por webhook. Não implementa
    PaymentGateway de propósito (não é síncrono); usada direto pela view.
    """

    def __init__(self, handle):
        if not handle:
            raise ValueError("InfiniteTag não configurado — defina em /painel/pagamento/.")
        self.handle = handle

    def criar_link(self, order_nsu, curso, valor, redirect_url, webhook_url, cliente=None):
        """Cria o link de pagamento hospedado. Retorna a URL pra redirecionar
        o cliente. Preço sempre em centavos."""
        payload = {
            "handle": self.handle,
            "order_nsu": order_nsu,
            "redirect_url": redirect_url,
            "webhook_url": webhook_url,
            "items": [
                {"description": curso.titulo[:64], "quantity": 1, "price": int(round(valor * 100))},
            ],
        }
        if cliente:
            payload["customer"] = cliente
        resposta = requests.post(INFINITEPAY_LINKS_URL, json=payload, timeout=15)
        if not resposta.ok:
            logger.error("InfinitePay recusou criar link (HTTP %s): %s", resposta.status_code, resposta.text)
            resposta.raise_for_status()
        return resposta.json()["url"]

    def checar_pagamento(self, order_nsu, transaction_nsu, slug):
        """Consulta manual de status — fallback pro caso do webhook atrasar
        ou não chegar. Requer transaction_nsu (só disponível depois que
        alguma notificação do InfinitePay, webhook ou retorno, já informou)."""
        payload = {
            "handle": self.handle, "order_nsu": order_nsu,
            "transaction_nsu": transaction_nsu, "slug": slug,
        }
        resposta = requests.post(INFINITEPAY_CHECK_URL, json=payload, timeout=15)
        resposta.raise_for_status()
        return resposta.json()

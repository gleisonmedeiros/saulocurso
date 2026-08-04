import json
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from cursos.models import Curso
from matriculas.models import Matricula

from .models import CobrancaExterna, ConfiguracaoPagamento, Pagamento

DADOS_CADASTRO = {
    "metodo": "pix", "nome": "Fulano de Tal", "cpf": "12345678901",
    "telefone": "22999999999", "email": "fulano@teste.com",
}


def _curso():
    return Curso.objects.create(
        titulo="Curso Teste", slug="curso-teste", descricao_curta="x", descricao="x", preco="100.00",
    )


def _mock_link_ok():
    return Mock(
        status_code=200,
        json=lambda: {"url": "https://checkout.infinitepay.com.br/handle-teste?lenc=abc"},
        raise_for_status=lambda: None,
    )


class InfinitePayCheckoutTests(TestCase):
    def setUp(self):
        self.curso = _curso()
        ConfiguracaoPagamento.objects.create(
            pk=1, gateway=ConfiguracaoPagamento.Gateway.INFINITEPAY, infinitepay_handle="handle-teste",
        )

    @patch("pagamentos.services.requests.post")
    def test_checkout_anonimo_cria_conta_pendente_pagamento_e_cobranca(self, mock_post):
        mock_post.return_value = _mock_link_ok()

        resposta = self.client.post(reverse("pagamentos:checkout", args=[self.curso.slug]), DADOS_CADASTRO)

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.url, "https://checkout.infinitepay.com.br/handle-teste?lenc=abc")

        aluno = User.objects.get(username="fulano@teste.com")
        self.assertFalse(aluno.has_usable_password())  # não dá pra logar antes de pagar

        pagamento = Pagamento.objects.get(aluno=aluno, curso=self.curso)
        self.assertEqual(pagamento.status, "pendente")

        cobranca = CobrancaExterna.objects.get(pagamento=pagamento)
        self.assertFalse(cobranca.confirmado)

        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["handle"], "handle-teste")
        self.assertEqual(payload["order_nsu"], cobranca.order_nsu)
        self.assertEqual(payload["items"][0]["price"], 10000)  # R$100,00 em centavos

    @patch("pagamentos.services.requests.post")
    def test_email_de_tentativa_nao_paga_pode_ser_reusado(self, mock_post):
        mock_post.return_value = _mock_link_ok()

        self.client.post(reverse("pagamentos:checkout", args=[self.curso.slug]), DADOS_CADASTRO)
        self.assertEqual(User.objects.filter(username="fulano@teste.com").count(), 1)
        primeiro_id = User.objects.get(username="fulano@teste.com").id

        # tenta de novo com o mesmo email, sem nunca ter pago — não pode dar erro nem duplicar
        resposta = self.client.post(reverse("pagamentos:checkout", args=[self.curso.slug]), DADOS_CADASTRO)
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(User.objects.filter(username="fulano@teste.com").count(), 1)
        self.assertEqual(User.objects.get(username="fulano@teste.com").id, primeiro_id)  # reusou, não duplicou
        self.assertEqual(Pagamento.objects.filter(aluno_id=primeiro_id).count(), 2)  # duas tentativas pendentes

    @patch("pagamentos.services.requests.post")
    def test_email_ja_pago_e_bloqueado(self, mock_post):
        mock_post.return_value = _mock_link_ok()
        self.client.post(reverse("pagamentos:checkout", args=[self.curso.slug]), DADOS_CADASTRO)
        cobranca = CobrancaExterna.objects.first()
        self.client.post(
            reverse("pagamentos:webhook_infinitepay"),
            data=json.dumps({"order_nsu": cobranca.order_nsu, "transaction_nsu": "txn123"}),
            content_type="application/json",
        )

        outro_curso = Curso.objects.create(
            titulo="Outro Curso", slug="outro-curso", descricao_curta="x", descricao="x", preco="50.00",
        )
        resposta = self.client.post(reverse("pagamentos:checkout", args=[outro_curso.slug]), DADOS_CADASTRO)
        self.assertEqual(resposta.status_code, 200)  # fica no form, com erro
        self.assertContains(resposta, "Já existe uma conta com este email")
        self.assertEqual(Pagamento.objects.filter(curso=outro_curso).count(), 0)

    def test_checkout_anonimo_sem_dados_nao_cria_nada(self):
        resposta = self.client.post(reverse("pagamentos:checkout", args=[self.curso.slug]), {"metodo": "pix"})
        self.assertEqual(resposta.status_code, 200)  # volta pro form com erro
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(Pagamento.objects.count(), 0)

    @patch("pagamentos.services.requests.post")
    def test_webhook_confirma_libera_matricula_e_manda_senha(self, mock_post):
        mock_post.return_value = _mock_link_ok()
        self.client.post(reverse("pagamentos:checkout", args=[self.curso.slug]), DADOS_CADASTRO)
        cobranca = CobrancaExterna.objects.select_related("pagamento__aluno").first()
        aluno = cobranca.pagamento.aluno

        resposta = self.client.post(
            reverse("pagamentos:webhook_infinitepay"),
            data=json.dumps({"order_nsu": cobranca.order_nsu, "transaction_nsu": "txn123"}),
            content_type="application/json",
        )
        self.assertEqual(resposta.status_code, 200)

        cobranca.refresh_from_db()
        self.assertTrue(cobranca.confirmado)
        self.assertEqual(cobranca.transaction_nsu, "txn123")

        cobranca.pagamento.refresh_from_db()
        self.assertEqual(cobranca.pagamento.status, "aprovado")

        aluno.refresh_from_db()
        self.assertTrue(aluno.has_usable_password())  # senha real já foi definida e enviada
        self.assertTrue(Matricula.objects.filter(aluno=aluno, curso=self.curso, ativo=True).exists())

        # cliente volta pra tela de aguardando -> loga sozinho e vai pra área do aluno
        resposta = self.client.get(reverse("pagamentos:aguardando"), {"ref": cobranca.order_nsu})
        self.assertRedirects(resposta, reverse("cursos:minha_area"), fetch_redirect_response=False)

    @patch("pagamentos.services.requests.post")
    def test_webhook_e_idempotente(self, mock_post):
        mock_post.return_value = _mock_link_ok()
        aluno = User.objects.create_user(username="logado@teste.com", email="logado@teste.com", password="x")
        self.client.force_login(aluno)
        self.client.post(reverse("pagamentos:checkout", args=[self.curso.slug]), {"metodo": "pix"})

        self.assertEqual(Pagamento.objects.filter(aluno=aluno, curso=self.curso).count(), 1)
        cobranca = CobrancaExterna.objects.first()

        payload = json.dumps({"order_nsu": cobranca.order_nsu, "transaction_nsu": "txn123"})
        for _ in range(3):
            self.client.post(
                reverse("pagamentos:webhook_infinitepay"), data=payload, content_type="application/json",
            )

        self.assertEqual(Pagamento.objects.filter(aluno=aluno, curso=self.curso).count(), 1)
        self.assertEqual(Matricula.objects.filter(aluno=aluno, curso=self.curso).count(), 1)
        self.assertEqual(Pagamento.objects.get(aluno=aluno, curso=self.curso).status, "aprovado")

    def test_webhook_rejeita_order_nsu_desconhecido(self):
        resposta = self.client.post(
            reverse("pagamentos:webhook_infinitepay"),
            data=json.dumps({"order_nsu": "nao-existe"}),
            content_type="application/json",
        )
        self.assertEqual(resposta.status_code, 400)

    @patch("pagamentos.services.requests.post")
    def test_aguardando_confirma_via_payment_check_quando_webhook_nao_chegou(self, mock_post):
        mock_post.return_value = _mock_link_ok()
        self.client.post(reverse("pagamentos:checkout", args=[self.curso.slug]), DADOS_CADASTRO)
        cobranca = CobrancaExterna.objects.first()
        self.assertFalse(cobranca.confirmado)

        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {"success": True, "paid": True, "amount": 10000, "capture_method": "pix"},
            raise_for_status=lambda: None,
        )
        resposta = self.client.get(reverse("pagamentos:aguardando"), {
            "ref": cobranca.order_nsu, "transaction_nsu": "txn-real-123", "slug": "abc123",
        })
        self.assertRedirects(resposta, reverse("cursos:minha_area"), fetch_redirect_response=False)

        cobranca.refresh_from_db()
        self.assertTrue(cobranca.confirmado)
        self.assertEqual(cobranca.transaction_nsu, "txn-real-123")

    @patch("pagamentos.services.requests.post")
    def test_aguardando_nao_confirma_se_payment_check_diz_nao_pago(self, mock_post):
        mock_post.return_value = _mock_link_ok()
        self.client.post(reverse("pagamentos:checkout", args=[self.curso.slug]), DADOS_CADASTRO)
        cobranca = CobrancaExterna.objects.first()

        mock_post.return_value = Mock(
            status_code=200, json=lambda: {"success": True, "paid": False}, raise_for_status=lambda: None,
        )
        resposta = self.client.get(reverse("pagamentos:aguardando"), {
            "ref": cobranca.order_nsu, "transaction_nsu": "txn-nao-pago", "slug": "abc123",
        })
        self.assertEqual(resposta.status_code, 200)  # continua na tela de espera

        cobranca.refresh_from_db()
        self.assertFalse(cobranca.confirmado)


class MockCheckoutTests(TestCase):
    """Gateway mock (padrão) — fluxo síncrono antigo, cadastro continua
    acontecendo DEPOIS do pagamento."""

    def setUp(self):
        self.curso = _curso()

    def test_checkout_anonimo_mock_manda_pro_cadastro_pos_pagamento(self):
        resposta = self.client.post(reverse("pagamentos:checkout", args=[self.curso.slug]), {"metodo": "pix"})
        self.assertRedirects(resposta, reverse("pagamentos:cadastro"))
        self.assertEqual(User.objects.count(), 0)  # ainda não criou conta

        resposta = self.client.post(reverse("pagamentos:cadastro"), {
            "nome": "Ciclano", "cpf": "98765432100", "telefone": "22988887777", "email": "ciclano@teste.com",
        })
        aluno = User.objects.get(username="ciclano@teste.com")
        self.assertTrue(Pagamento.objects.filter(aluno=aluno, curso=self.curso, status="aprovado").exists())
        self.assertTrue(Matricula.objects.filter(aluno=aluno, curso=self.curso, ativo=True).exists())

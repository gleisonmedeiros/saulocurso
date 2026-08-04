import json
import logging
import secrets

import requests
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import Perfil
from cursos.models import Curso
from matriculas.models import Matricula
from notificacoes.services import NotificationService

from .forms import CadastroAlunoForm
from .models import CobrancaExterna, ConfiguracaoPagamento, Pagamento
from .services import InfinitePayGateway, get_payment_gateway

logger = logging.getLogger(__name__)

SESSION_KEY_CURSO_PENDENTE = "pagamento_pendente_curso_id"
SESSION_KEY_METODO_PENDENTE = "pagamento_pendente_metodo"
SESSION_KEY_ORDER_NSU = "pagamento_pendente_order_nsu"
METODOS_VALIDOS = {"pix", "cartao"}


def checkout(request, slug):
    curso = get_object_or_404(Curso, slug=slug, ativo=True)

    if request.user.is_authenticated and Matricula.objects.filter(aluno=request.user, curso=curso, ativo=True).exists():
        messages.info(request, "Você já está matriculado neste curso.")
        return redirect("cursos:conteudo", slug=curso.slug)

    config_pagamento = ConfiguracaoPagamento.obter()
    usa_infinitepay = config_pagamento.gateway == ConfiguracaoPagamento.Gateway.INFINITEPAY
    # InfinitePay é assíncrono (redireciona + webhook depois) — se o cliente
    # ainda não tem conta, precisa coletar os dados JÁ no checkout, senão não
    # tem como criar a conta/mandar a senha quando a confirmação chegar sem
    # ele estar presente pra preencher um cadastro depois.
    precisa_cadastro_previo = usa_infinitepay and not request.user.is_authenticated

    if request.method == "POST":
        metodo = request.POST.get("metodo")
        if metodo not in METODOS_VALIDOS:
            metodo = "pix"

        if usa_infinitepay:
            cadastro_form = None
            if precisa_cadastro_previo:
                cadastro_form = CadastroAlunoForm(request.POST)
                if not cadastro_form.is_valid():
                    return render(request, "pagamentos/checkout.html", {
                        "curso": curso, "payment_gateway": config_pagamento.gateway, "cadastro_form": cadastro_form,
                    })
            return _iniciar_checkout_infinitepay(request, curso, metodo, config_pagamento, cadastro_form)

        # Mock — síncrono, aprova/recusa na hora, fluxo antigo intacto.
        gateway = get_payment_gateway()
        resultado = gateway.cobrar(request.user if request.user.is_authenticated else None, curso, curso.preco)

        if not resultado.aprovado:
            messages.error(request, "Pagamento recusado.")
            return render(request, "pagamentos/checkout.html", {"curso": curso, "payment_gateway": config_pagamento.gateway})

        if request.user.is_authenticated:
            Pagamento.objects.create(aluno=request.user, curso=curso, valor=curso.preco, status="aprovado", metodo=metodo)
            Matricula.objects.get_or_create(aluno=request.user, curso=curso, defaults={"ativo": True})
            NotificationService().notificar_matricula(request.user, curso)
            messages.success(request, "Pagamento aprovado! Curso liberado na sua área.")
            return redirect("cursos:minha_area")

        request.session[SESSION_KEY_CURSO_PENDENTE] = curso.id
        request.session[SESSION_KEY_METODO_PENDENTE] = metodo
        messages.success(request, "Pagamento aprovado! Complete seu cadastro pra liberar o acesso.")
        return redirect("pagamentos:cadastro")

    cadastro_form = CadastroAlunoForm() if precisa_cadastro_previo else None
    return render(request, "pagamentos/checkout.html", {
        "curso": curso, "payment_gateway": config_pagamento.gateway, "cadastro_form": cadastro_form,
    })


def _criar_conta_pendente(dados):
    """Cria a conta ANTES do pagamento, com senha inutilizável de propósito
    — ninguém consegue logar até a gente mesma definir a senha de verdade,
    quando o pagamento for confirmado (ver _marcar_confirmado).

    Se já existir uma conta com esse email de uma tentativa anterior que não
    chegou a pagar (o clean_email do form só bloqueia quem JÁ pagou), reaproveita
    em vez de tentar criar de novo — username é único, duplicar quebraria.
    Retorna (aluno, criado_agora) — criado_agora=False significa que é reuso,
    então não deve ser apagado se o link do InfinitePay falhar depois."""
    aluno = User.objects.filter(username__iexact=dados["email"]).first()
    if aluno:
        aluno.first_name = dados["nome"]
        aluno.save(update_fields=["first_name"])
        Perfil.objects.update_or_create(
            user=aluno, defaults={"telefone": dados["telefone"], "cpf": dados["cpf"], "deve_trocar_senha": True},
        )
        return aluno, False

    aluno = User.objects.create_user(username=dados["email"], email=dados["email"], first_name=dados["nome"])
    aluno.set_unusable_password()
    aluno.save()
    Perfil.objects.create(user=aluno, telefone=dados["telefone"], cpf=dados["cpf"], deve_trocar_senha=True)
    return aluno, True


def _iniciar_checkout_infinitepay(request, curso, metodo, config_pagamento, cadastro_form):
    aluno_criado_agora = False
    if request.user.is_authenticated:
        aluno = request.user
    else:
        aluno, aluno_criado_agora = _criar_conta_pendente(cadastro_form.cleaned_data)

    order_nsu = secrets.token_urlsafe(16)
    pagamento = Pagamento.objects.create(aluno=aluno, curso=curso, valor=curso.preco, status="pendente", metodo=metodo)
    cobranca = CobrancaExterna.objects.create(order_nsu=order_nsu, pagamento=pagamento)

    redirect_url = request.build_absolute_uri(reverse("pagamentos:aguardando")) + f"?ref={order_nsu}"
    webhook_url = request.build_absolute_uri(reverse("pagamentos:webhook_infinitepay"))
    cliente = {"name": aluno.get_full_name() or aluno.username, "email": aluno.email} if aluno.email else None

    try:
        gateway = InfinitePayGateway(config_pagamento.infinitepay_handle)
        url_pagamento = gateway.criar_link(order_nsu, curso, curso.preco, redirect_url, webhook_url, cliente)
    except (ValueError, requests.RequestException):
        cobranca.delete()
        pagamento.delete()
        if aluno_criado_agora:
            aluno.delete()
        messages.error(request, "Não deu pra iniciar o pagamento agora. Tenta de novo em instantes.")
        return render(request, "pagamentos/checkout.html", {
            "curso": curso, "payment_gateway": config_pagamento.gateway,
            "cadastro_form": CadastroAlunoForm() if not request.user.is_authenticated else None,
        })

    request.session[SESSION_KEY_ORDER_NSU] = order_nsu
    return redirect(url_pagamento)


def aguardando_confirmacao(request):
    """Pra onde o InfinitePay manda o cliente de volta depois do pagamento.
    A confirmação principal vem do webhook (server-to-server), mas o
    InfinitePay também manda transaction_nsu+slug na URL de retorno — usamos
    isso pra consultar o payment_check como reforço (cobre o caso do webhook
    atrasar, falhar, ou não conseguir alcançar o servidor, tipo em dev local
    sem URL pública)."""
    order_nsu = request.GET.get("ref") or request.session.get(SESSION_KEY_ORDER_NSU)
    if not order_nsu:
        messages.error(request, "Nenhum pagamento em andamento encontrado.")
        return redirect("cursos:lista")

    cobranca = CobrancaExterna.objects.filter(order_nsu=order_nsu).select_related("pagamento__curso", "pagamento__aluno").first()
    if not cobranca:
        messages.error(request, "Pagamento não encontrado.")
        return redirect("cursos:lista")

    if not cobranca.confirmado:
        transaction_nsu = request.GET.get("transaction_nsu")
        slug = request.GET.get("slug")
        if transaction_nsu and slug:
            _tentar_confirmar_via_payment_check(cobranca, transaction_nsu, slug)

    if not cobranca.confirmado:
        return render(request, "pagamentos/aguardando.html", {"curso": cobranca.pagamento.curso, "order_nsu": order_nsu})

    if not request.user.is_authenticated:
        login(request, cobranca.pagamento.aluno)
    messages.success(request, "Pagamento aprovado! Curso liberado na sua área.")
    return redirect("cursos:minha_area")


def _marcar_confirmado(cobranca, transaction_nsu):
    """Idempotente — webhook e o fallback de payment_check podem chamar isso
    pro mesmo pagamento, não pode duplicar Matricula nem reenviar a senha."""
    if cobranca.confirmado:
        return
    cobranca.confirmado = True
    cobranca.transaction_nsu = transaction_nsu or ""
    cobranca.confirmado_em = timezone.now()
    cobranca.save()

    pagamento = cobranca.pagamento
    pagamento.status = "aprovado"
    pagamento.save(update_fields=["status"])

    aluno = pagamento.aluno
    Matricula.objects.get_or_create(aluno=aluno, curso=pagamento.curso, defaults={"ativo": True})

    # Pagamento confirmado e matrícula liberada acima são o que importa de
    # verdade — se o envio de email falhar (SMTP fora do ar etc), isso NÃO
    # pode desfazer o acesso ao curso. Só loga pra resolver manualmente.
    notificacao = NotificationService()
    try:
        notificacao.notificar_matricula(aluno, pagamento.curso)
    except Exception:
        logger.exception("Falha ao notificar matrícula pra %s (curso %s)", aluno.username, pagamento.curso_id)

    if not aluno.has_usable_password():
        # Conta criada no checkout, antes de confirmar o pagamento — só
        # agora, com o pagamento de verdade, geramos e mandamos a senha.
        senha_temporaria = secrets.token_urlsafe(9)
        aluno.set_password(senha_temporaria)
        aluno.save()
        try:
            notificacao.notificar_credenciais(aluno, senha_temporaria)
        except Exception:
            logger.exception(
                "Falha ao enviar credenciais pra %s — senha foi definida mas email não confirmado. "
                "Precisa resetar/reenviar manualmente.", aluno.username,
            )


def _tentar_confirmar_via_payment_check(cobranca, transaction_nsu, slug):
    """Fallback pro caso do webhook não chegar (dev local sem URL pública,
    atraso, falha de rede) — consulta o InfinitePay direto usando os dados
    que ele manda na URL de retorno."""
    config = ConfiguracaoPagamento.obter()
    if not config.infinitepay_handle:
        return
    try:
        gateway = InfinitePayGateway(config.infinitepay_handle)
        resultado = gateway.checar_pagamento(cobranca.order_nsu, transaction_nsu, slug)
    except (ValueError, requests.RequestException):
        return

    if resultado.get("paid"):
        _marcar_confirmado(cobranca, transaction_nsu)


@csrf_exempt
@require_POST
def webhook_infinitepay(request):
    try:
        dados = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"success": False}, status=400)

    order_nsu = dados.get("order_nsu")
    if not order_nsu:
        return JsonResponse({"success": False}, status=400)

    cobranca = CobrancaExterna.objects.filter(order_nsu=order_nsu).select_related("pagamento").first()
    if not cobranca:
        return JsonResponse({"success": False}, status=400)

    _marcar_confirmado(cobranca, dados.get("transaction_nsu", ""))
    return JsonResponse({"success": True})


def cadastro_pos_pagamento(request):
    """Só usado pelo gateway mock (síncrono) — no InfinitePay o cadastro
    acontece ANTES do pagamento, direto no checkout (ver _criar_conta_pendente)."""
    curso_id = request.session.get(SESSION_KEY_CURSO_PENDENTE)
    if not curso_id:
        messages.error(request, "Nenhum pagamento pendente encontrado. Escolha um curso pra começar.")
        return redirect("cursos:lista")

    curso = get_object_or_404(Curso, id=curso_id)

    if request.method == "POST":
        form = CadastroAlunoForm(request.POST)
        if form.is_valid():
            senha_temporaria = secrets.token_urlsafe(9)

            aluno = User.objects.create_user(
                username=form.cleaned_data["email"],
                email=form.cleaned_data["email"],
                password=senha_temporaria,
                first_name=form.cleaned_data["nome"],
            )
            Perfil.objects.create(
                user=aluno,
                telefone=form.cleaned_data["telefone"],
                cpf=form.cleaned_data["cpf"],
                deve_trocar_senha=True,
            )
            metodo = request.session.get(SESSION_KEY_METODO_PENDENTE, "pix")
            Pagamento.objects.create(aluno=aluno, curso=curso, valor=curso.preco, status="aprovado", metodo=metodo)
            Matricula.objects.get_or_create(aluno=aluno, curso=curso, defaults={"ativo": True})

            notificacao = NotificationService()
            try:
                notificacao.notificar_matricula(aluno, curso)
                notificacao.notificar_credenciais(aluno, senha_temporaria)
            except Exception:
                logger.exception("Falha ao notificar/enviar credenciais pra %s", aluno.username)

            del request.session[SESSION_KEY_CURSO_PENDENTE]
            request.session.pop(SESSION_KEY_METODO_PENDENTE, None)
            login(request, aluno)
            request.session["credenciais_demo"] = {"login": aluno.username, "senha": senha_temporaria}
            messages.success(request, "Cadastro concluído! Enviamos sua senha temporária por email.")
            return redirect("accounts:trocar_senha")
    else:
        form = CadastroAlunoForm()

    return render(request, "pagamentos/cadastro.html", {"curso": curso, "form": form})

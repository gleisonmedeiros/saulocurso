import secrets

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Perfil
from cursos.models import Curso
from matriculas.models import Matricula
from notificacoes.services import NotificationService

from .forms import CadastroPosPagamentoForm
from .models import Pagamento
from .services import get_payment_gateway

SESSION_KEY_CURSO_PENDENTE = "pagamento_pendente_curso_id"
SESSION_KEY_METODO_PENDENTE = "pagamento_pendente_metodo"
METODOS_VALIDOS = {"pix", "cartao"}


def checkout(request, slug):
    curso = get_object_or_404(Curso, slug=slug, ativo=True)

    if request.user.is_authenticated and Matricula.objects.filter(aluno=request.user, curso=curso, ativo=True).exists():
        messages.info(request, "Você já está matriculado neste curso.")
        return redirect("cursos:conteudo", slug=curso.slug)

    if request.method == "POST":
        metodo = request.POST.get("metodo")
        if metodo not in METODOS_VALIDOS:
            metodo = "pix"

        gateway = get_payment_gateway()
        resultado = gateway.cobrar(request.user if request.user.is_authenticated else None, curso, curso.preco)

        if not resultado.aprovado:
            messages.error(request, "Pagamento recusado.")
            return render(request, "pagamentos/checkout.html", {"curso": curso})

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

    return render(request, "pagamentos/checkout.html", {"curso": curso})


def cadastro_pos_pagamento(request):
    curso_id = request.session.get(SESSION_KEY_CURSO_PENDENTE)
    if not curso_id:
        messages.error(request, "Nenhum pagamento pendente encontrado. Escolha um curso pra começar.")
        return redirect("cursos:lista")

    curso = get_object_or_404(Curso, id=curso_id)

    if request.method == "POST":
        form = CadastroPosPagamentoForm(request.POST)
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
            notificacao.notificar_matricula(aluno, curso)
            notificacao.notificar_credenciais(aluno, senha_temporaria)

            del request.session[SESSION_KEY_CURSO_PENDENTE]
            request.session.pop(SESSION_KEY_METODO_PENDENTE, None)
            login(request, aluno)
            request.session["credenciais_demo"] = {"login": aluno.username, "senha": senha_temporaria}
            messages.success(request, "Cadastro concluído! Enviamos sua senha temporária por email.")
            return redirect("accounts:trocar_senha")
    else:
        form = CadastroPosPagamentoForm()

    return render(request, "pagamentos/cadastro.html", {"curso": curso, "form": form})

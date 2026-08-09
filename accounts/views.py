import logging
import secrets
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password, make_password
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from notificacoes.services import NotificationService

from .forms import CodigoForm, EsqueciSenhaForm, NovaSenhaForm, TrocarSenhaForm
from .models import CodigoRecuperacaoSenha

logger = logging.getLogger(__name__)
User = get_user_model()

# A conta do aluno é criada durante o checkout (pagamentos/views.py), não aqui.

# Chaves de sessão do fluxo de recuperação de senha.
SESSION_UID = "rec_uid"          # id do usuário que pediu recuperação (0 = email não encontrado)
SESSION_VERIFICADO = "rec_ok"    # código conferido, pode redefinir a senha
CODIGO_VALIDADE_MIN = 15


@login_required
def trocar_senha(request):
    if request.method == "POST":
        form = TrocarSenhaForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)

            perfil = getattr(user, "perfil", None)
            if perfil and perfil.deve_trocar_senha:
                perfil.deve_trocar_senha = False
                perfil.save(update_fields=["deve_trocar_senha"])

            request.session.pop("credenciais_demo", None)
            messages.success(request, "Senha alterada com sucesso!")
            return redirect("cursos:minha_area")
    else:
        form = TrocarSenhaForm(request.user)

    credenciais_demo = request.session.get("credenciais_demo")
    return render(request, "accounts/trocar_senha.html", {"form": form, "credenciais_demo": credenciais_demo})


# --- Recuperação de senha (esqueci a senha) ---------------------------------

def esqueci_senha(request):
    """Passo 1: aluno informa o email. Se existir, gera um código, guarda o
    hash e envia por email. A mensagem é sempre a mesma (exista ou não) pra
    não revelar quais emails têm conta."""
    if request.method == "POST":
        form = EsqueciSenhaForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()
            user = (
                User.objects.filter(email__iexact=email).first()
                or User.objects.filter(username__iexact=email).first()
            )
            if user:
                # invalida códigos anteriores ainda em aberto
                CodigoRecuperacaoSenha.objects.filter(user=user, usado=False).update(usado=True)
                codigo = f"{secrets.randbelow(10 ** 6):06d}"
                CodigoRecuperacaoSenha.objects.create(
                    user=user,
                    codigo_hash=make_password(codigo),
                    expira_em=timezone.now() + timedelta(minutes=CODIGO_VALIDADE_MIN),
                )
                try:
                    NotificationService().notificar_codigo_recuperacao(user, codigo)
                except Exception:
                    logger.exception("Falha ao enviar código de recuperação pra %s", user.pk)
                request.session[SESSION_UID] = user.pk
            else:
                request.session[SESSION_UID] = 0

            request.session.pop(SESSION_VERIFICADO, None)
            messages.success(
                request,
                "Se o email estiver cadastrado, enviamos um código de verificação. "
                "Confira sua caixa de entrada (e o spam) e digite o código abaixo.",
            )
            return redirect("accounts:verificar_codigo")
    else:
        form = EsqueciSenhaForm()
    return render(request, "accounts/esqueci_senha.html", {"form": form})


def verificar_codigo(request):
    """Passo 2: aluno digita o código. Confere contra o hash, com expiração e
    limite de tentativas."""
    uid = request.session.get(SESSION_UID)
    if uid is None:
        return redirect("accounts:esqueci_senha")

    if request.method == "POST":
        form = CodigoForm(request.POST)
        if form.is_valid():
            codigo = form.cleaned_data["codigo"]
            registro = (
                CodigoRecuperacaoSenha.objects.filter(user_id=uid, usado=False).order_by("-criado_em").first()
                if uid else None
            )
            if registro and registro.valido() and check_password(codigo, registro.codigo_hash):
                registro.usado = True
                registro.save(update_fields=["usado"])
                request.session[SESSION_VERIFICADO] = True
                return redirect("accounts:redefinir_senha")

            if registro and not registro.usado:
                registro.tentativas += 1
                registro.save(update_fields=["tentativas"])
                restantes = registro.MAX_TENTATIVAS - registro.tentativas
                if restantes <= 0:
                    messages.error(request, "Muitas tentativas. Peça um novo código.")
                    return redirect("accounts:esqueci_senha")
                messages.error(request, f"Código inválido ou expirado. Tentativas restantes: {restantes}.")
            else:
                messages.error(request, "Código inválido ou expirado. Peça um novo código.")
    else:
        form = CodigoForm()
    return render(request, "accounts/verificar_codigo.html", {"form": form})


def redefinir_senha(request):
    """Passo 3: código conferido, aluno escolhe a nova senha (dois campos)."""
    uid = request.session.get(SESSION_UID)
    if not uid or not request.session.get(SESSION_VERIFICADO):
        return redirect("accounts:esqueci_senha")

    user = get_object_or_404(User, pk=uid)
    if request.method == "POST":
        form = NovaSenhaForm(user, request.POST)
        if form.is_valid():
            form.save()
            request.session.pop(SESSION_UID, None)
            request.session.pop(SESSION_VERIFICADO, None)

            perfil = getattr(user, "perfil", None)
            if perfil and perfil.deve_trocar_senha:
                perfil.deve_trocar_senha = False
                perfil.save(update_fields=["deve_trocar_senha"])

            messages.success(request, "Senha redefinida com sucesso! Entre com a nova senha.")
            return redirect("accounts:login")
    else:
        form = NovaSenhaForm(user)
    return render(request, "accounts/redefinir_senha.html", {"form": form})

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import TrocarSenhaForm

# A conta do aluno é criada durante o checkout (pagamentos/views.py), não aqui.


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

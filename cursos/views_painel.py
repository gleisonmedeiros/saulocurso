import logging
import secrets

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import Perfil
from matriculas.models import Certificado, InscricaoTurma, InteresseTurma, Matricula
from matriculas.progresso import calcular_progresso
from notificacoes.emails import MODELOS as MODELOS_EMAIL
from notificacoes.models import ConfiguracaoNotificacao, ModeloEmail
from notificacoes.services import NotificationService
from pagamentos.models import ConfiguracaoPagamento, Pagamento

from .forms_painel import (
    AlunoEditForm, AulaForm, ConfiguracaoNotificacaoForm, ConfiguracaoPagamentoForm, ConfiguracaoSiteForm, CupomForm,
    CursoForm, MatricularAlunoForm, MentoriaForm, ModuloForm, PerguntaFrequenteForm, TurmaForm,
)
from .models import (
    Aula, ConfiguracaoSite, ContatoMensagem, Cupom, Curso, MentoriaAoVivo, Modulo, PerguntaFrequente, Turma,
)

User = get_user_model()
logger = logging.getLogger(__name__)


def _notificar_mentoria(request, mentoria):
    try:
        enviados = NotificationService().notificar_mentoria(mentoria)
        if enviados:
            messages.info(request, f"{enviados} aluno(s) avisado(s) por email sobre a mentoria.")
    except Exception:
        logger.exception("Falha ao notificar mentoria %s", mentoria.pk)


def _notificar_interessados_turma(request, turma):
    if not turma.esta_aberta():
        return
    interessados = list(InteresseTurma.objects.filter(curso=turma.curso, notificado_em__isnull=True).select_related("aluno"))
    if not interessados:
        return
    try:
        enviados = NotificationService().notificar_turma_aberta(interessados, turma)
        if enviados:
            InteresseTurma.objects.filter(pk__in=[i.pk for i in interessados]).update(notificado_em=timezone.now())
            messages.info(request, f"{enviados} interessado(s) avisado(s) por email sobre a turma nova.")
    except Exception:
        logger.exception("Falha ao notificar interessados da turma %s", turma.pk)


@staff_member_required
def dashboard(request):
    cursos = Curso.objects.all()
    return render(request, "painel/dashboard.html", {"cursos": cursos})


@staff_member_required
def configuracoes(request):
    config = ConfiguracaoSite.obter()
    if request.method == "POST":
        form = ConfiguracaoSiteForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, "Configurações do site atualizadas.")
            return redirect("painel:dashboard")
    else:
        form = ConfiguracaoSiteForm(instance=config)
    return render(request, "painel/configuracoes_form.html", {"form": form})


@staff_member_required
def pagamento_config(request):
    config = ConfiguracaoPagamento.obter()
    if request.method == "POST":
        form = ConfiguracaoPagamentoForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, "Configuração de pagamento atualizada.")
            return redirect("painel:dashboard")
    else:
        form = ConfiguracaoPagamentoForm(instance=config)
    return render(request, "painel/pagamento_form.html", {"form": form})


@staff_member_required
def notificacoes_config(request):
    config = ConfiguracaoNotificacao.obter()
    if request.method == "POST":
        form = ConfiguracaoNotificacaoForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, "Configuração de notificações atualizada.")
            return redirect("painel:dashboard")
    else:
        form = ConfiguracaoNotificacaoForm(instance=config)
    return render(request, "painel/notificacoes_form.html", {"form": form})


# --- Modelos de email --------------------------------------------------------

@staff_member_required
def modelos_email_lista(request):
    modelos = []
    for chave, meta in MODELOS_EMAIL.items():
        row = ModeloEmail.objects.filter(chave=chave).first()
        personalizado = bool(row and (row.assunto.strip() or row.corpo.strip()))
        modelos.append({
            "chave": chave, "nome": meta["nome"], "descricao": meta["descricao"],
            "personalizado": personalizado,
        })
    return render(request, "painel/modelos_email_lista.html", {"modelos": modelos})


@staff_member_required
def modelo_email_editar(request, chave):
    meta = MODELOS_EMAIL.get(chave)
    if not meta:
        raise Http404("Modelo de email não encontrado.")
    row, _ = ModeloEmail.objects.get_or_create(chave=chave)

    if request.method == "POST":
        if "restaurar" in request.POST:
            row.assunto = ""
            row.corpo = ""
            row.save()
            messages.success(request, "Modelo restaurado para o texto padrão.")
            return redirect("painel:modelo_email_editar", chave=chave)
        row.assunto = (request.POST.get("assunto") or "").strip()
        row.corpo = (request.POST.get("corpo") or "").strip()
        row.save()
        messages.success(request, "Modelo de email salvo.")
        return redirect("painel:modelos_email_lista")

    return render(request, "painel/modelo_email_form.html", {
        "chave": chave, "meta": meta,
        "assunto": row.assunto or meta["assunto"],
        "corpo": row.corpo or meta["corpo"],
        "personalizado": bool(row.assunto or row.corpo),
    })


# --- Curso -----------------------------------------------------------------

@staff_member_required
def cursos_ordenar(request):
    """Reordena os cursos da home arrastando. O POST recebe a lista de ids na
    nova ordem e regrava o campo `ordem` sequencialmente (0,1,2...)."""
    if request.method == "POST":
        ids = request.POST.getlist("ordem")
        pks = [int(i) for i in ids if i.isdigit()]
        cursos = Curso.objects.in_bulk(pks)
        for posicao, pk in enumerate(pks):
            curso = cursos.get(pk)
            if curso and curso.ordem != posicao:
                curso.ordem = posicao
                curso.save(update_fields=["ordem"])
        messages.success(request, "Ordem dos cursos atualizada.")
        return redirect("painel:cursos_ordenar")

    cursos = Curso.objects.all()  # já vem por ordem (Meta.ordering)
    return render(request, "painel/cursos_ordenar.html", {"cursos": cursos})


@staff_member_required
def curso_detalhe(request, pk):
    curso = get_object_or_404(Curso, pk=pk)
    modulos = curso.modulos.prefetch_related("aulas")
    mentorias = curso.mentorias.all()
    turmas = curso.turmas.all()
    return render(request, "painel/curso_detalhe.html", {
        "curso": curso, "modulos": modulos, "mentorias": mentorias, "turmas": turmas,
    })


@staff_member_required
def curso_novo(request):
    if request.method == "POST":
        form = CursoForm(request.POST, request.FILES)
        if form.is_valid():
            curso = form.save()
            messages.success(request, "Curso criado.")
            return redirect("painel:curso_detalhe", pk=curso.pk)
    else:
        form = CursoForm()
    return render(request, "painel/curso_form.html", {"form": form, "titulo_pagina": "Novo curso"})


@staff_member_required
def curso_editar(request, pk):
    curso = get_object_or_404(Curso, pk=pk)
    if request.method == "POST":
        form = CursoForm(request.POST, request.FILES, instance=curso)
        if form.is_valid():
            form.save()
            messages.success(request, "Curso atualizado.")
            return redirect("painel:curso_detalhe", pk=curso.pk)
    else:
        form = CursoForm(instance=curso)
    return render(request, "painel/curso_form.html", {"form": form, "titulo_pagina": f"Editar — {curso.titulo}", "curso": curso})


@staff_member_required
def curso_excluir(request, pk):
    curso = get_object_or_404(Curso, pk=pk)
    if request.method == "POST":
        curso.delete()
        messages.success(request, "Curso excluído.")
        return redirect("painel:dashboard")
    return render(request, "painel/confirmar_exclusao.html", {"objeto": curso, "voltar_url": "painel:curso_detalhe", "voltar_pk": curso.pk})


# --- Modulo ------------------------------------------------------------------

@staff_member_required
def modulo_novo(request, curso_pk):
    curso = get_object_or_404(Curso, pk=curso_pk)
    if request.method == "POST":
        form = ModuloForm(request.POST)
        if form.is_valid():
            modulo = form.save(commit=False)
            modulo.curso = curso
            modulo.save()
            messages.success(request, "Módulo criado.")
            return redirect("painel:curso_detalhe", pk=curso.pk)
    else:
        form = ModuloForm()
    return render(request, "painel/modulo_form.html", {"form": form, "curso": curso, "titulo_pagina": "Novo módulo"})


@staff_member_required
def modulo_editar(request, pk):
    modulo = get_object_or_404(Modulo, pk=pk)
    if request.method == "POST":
        form = ModuloForm(request.POST, instance=modulo)
        if form.is_valid():
            form.save()
            messages.success(request, "Módulo atualizado.")
            return redirect("painel:curso_detalhe", pk=modulo.curso.pk)
    else:
        form = ModuloForm(instance=modulo)
    return render(request, "painel/modulo_form.html", {"form": form, "curso": modulo.curso, "titulo_pagina": f"Editar — {modulo.titulo}"})


@staff_member_required
def modulo_excluir(request, pk):
    modulo = get_object_or_404(Modulo, pk=pk)
    curso = modulo.curso
    if request.method == "POST":
        modulo.delete()
        messages.success(request, "Módulo excluído.")
        return redirect("painel:curso_detalhe", pk=curso.pk)
    return render(request, "painel/confirmar_exclusao.html", {"objeto": modulo, "voltar_url": "painel:curso_detalhe", "voltar_pk": curso.pk})


# --- Aula ----------------------------------------------------------------

@staff_member_required
def aula_nova(request, modulo_pk):
    modulo = get_object_or_404(Modulo, pk=modulo_pk)
    if request.method == "POST":
        form = AulaForm(request.POST, request.FILES)
        if form.is_valid():
            aula = form.save(commit=False)
            aula.modulo = modulo
            aula.save()
            messages.success(request, "Aula criada.")
            return redirect("painel:curso_detalhe", pk=modulo.curso.pk)
    else:
        form = AulaForm()
    return render(request, "painel/aula_form.html", {"form": form, "modulo": modulo, "titulo_pagina": "Nova aula"})


@staff_member_required
def aula_editar(request, pk):
    aula = get_object_or_404(Aula, pk=pk)
    if request.method == "POST":
        form = AulaForm(request.POST, request.FILES, instance=aula)
        if form.is_valid():
            form.save()
            messages.success(request, "Aula atualizada.")
            return redirect("painel:curso_detalhe", pk=aula.modulo.curso.pk)
    else:
        form = AulaForm(instance=aula)
    return render(request, "painel/aula_form.html", {"form": form, "modulo": aula.modulo, "titulo_pagina": f"Editar — {aula.titulo}"})


@staff_member_required
def aula_excluir(request, pk):
    aula = get_object_or_404(Aula, pk=pk)
    curso = aula.modulo.curso
    if request.method == "POST":
        aula.delete()
        messages.success(request, "Aula excluída.")
        return redirect("painel:curso_detalhe", pk=curso.pk)
    return render(request, "painel/confirmar_exclusao.html", {"objeto": aula, "voltar_url": "painel:curso_detalhe", "voltar_pk": curso.pk})


# --- Mentoria ----------------------------------------------------------------

@staff_member_required
def mentoria_nova(request, curso_pk):
    curso = get_object_or_404(Curso, pk=curso_pk)
    if request.method == "POST":
        form = MentoriaForm(request.POST)
        if form.is_valid():
            mentoria = form.save(commit=False)
            mentoria.curso = curso
            mentoria.save()
            _notificar_mentoria(request, mentoria)
            messages.success(request, "Mentoria agendada.")
            return redirect("painel:curso_detalhe", pk=curso.pk)
    else:
        form = MentoriaForm()
    return render(request, "painel/mentoria_form.html", {"form": form, "curso": curso, "titulo_pagina": "Nova mentoria"})


@staff_member_required
def mentoria_editar(request, pk):
    mentoria = get_object_or_404(MentoriaAoVivo, pk=pk)
    if request.method == "POST":
        form = MentoriaForm(request.POST, instance=mentoria)
        if form.is_valid():
            mentoria = form.save()
            _notificar_mentoria(request, mentoria)
            messages.success(request, "Mentoria atualizada.")
            return redirect("painel:curso_detalhe", pk=mentoria.curso.pk)
    else:
        form = MentoriaForm(instance=mentoria)
    return render(request, "painel/mentoria_form.html", {"form": form, "curso": mentoria.curso, "titulo_pagina": f"Editar — {mentoria.titulo}"})


@staff_member_required
def mentoria_excluir(request, pk):
    mentoria = get_object_or_404(MentoriaAoVivo, pk=pk)
    curso = mentoria.curso
    if request.method == "POST":
        mentoria.delete()
        messages.success(request, "Mentoria excluída.")
        return redirect("painel:curso_detalhe", pk=curso.pk)
    return render(request, "painel/confirmar_exclusao.html", {"objeto": mentoria, "voltar_url": "painel:curso_detalhe", "voltar_pk": curso.pk})


# --- Turma ---------------------------------------------------------------

@staff_member_required
def turma_nova(request, curso_pk):
    curso = get_object_or_404(Curso, pk=curso_pk)
    if request.method == "POST":
        form = TurmaForm(request.POST)
        if form.is_valid():
            turma = form.save(commit=False)
            turma.curso = curso
            turma.save()
            messages.success(request, "Turma agendada.")
            _notificar_interessados_turma(request, turma)
            return redirect("painel:curso_detalhe", pk=curso.pk)
    else:
        form = TurmaForm()
    return render(request, "painel/turma_form.html", {"form": form, "curso": curso, "titulo_pagina": "Nova turma"})


@staff_member_required
def turma_editar(request, pk):
    turma = get_object_or_404(Turma, pk=pk)
    if request.method == "POST":
        form = TurmaForm(request.POST, instance=turma)
        if form.is_valid():
            form.save()
            messages.success(request, "Turma atualizada.")
            return redirect("painel:curso_detalhe", pk=turma.curso.pk)
    else:
        form = TurmaForm(instance=turma)
    return render(request, "painel/turma_form.html", {"form": form, "curso": turma.curso, "titulo_pagina": "Editar turma"})


@staff_member_required
def turma_excluir(request, pk):
    turma = get_object_or_404(Turma, pk=pk)
    curso = turma.curso
    if request.method == "POST":
        turma.delete()
        messages.success(request, "Turma excluída.")
        return redirect("painel:curso_detalhe", pk=curso.pk)
    return render(request, "painel/confirmar_exclusao.html", {"objeto": turma, "voltar_url": "painel:curso_detalhe", "voltar_pk": curso.pk})


# --- Agenda de turmas ----------------------------------------------------------

@staff_member_required
def agenda_turmas(request):
    turmas = Turma.objects.select_related("curso").order_by("-data_inicio")
    curso_id = request.GET.get("curso")
    if curso_id:
        turmas = turmas.filter(curso_id=curso_id)

    for turma in turmas:
        turma.ocupadas = turma.vagas_ocupadas()
        turma.disponiveis = turma.vagas_disponiveis()

    return render(request, "painel/agenda_turmas.html", {
        "turmas": turmas, "cursos": Curso.objects.order_by("titulo"), "curso_id": curso_id,
    })


@staff_member_required
def agenda_turma_detalhe(request, pk):
    turma = get_object_or_404(Turma.objects.select_related("curso"), pk=pk)
    inscritos = InscricaoTurma.objects.filter(turma=turma).select_related("aluno", "aluno__perfil")
    interessados = InteresseTurma.objects.filter(curso=turma.curso, notificado_em__isnull=True).select_related("aluno", "aluno__perfil")
    return render(request, "painel/agenda_turma_detalhe.html", {
        "turma": turma, "inscritos": inscritos, "interessados": interessados,
    })


# --- Cupons de desconto -------------------------------------------------------

@staff_member_required
def cupom_lista(request):
    cupons = Cupom.objects.all()
    return render(request, "painel/cupom_lista.html", {"cupons": cupons})


@staff_member_required
def cupom_novo(request):
    if request.method == "POST":
        form = CupomForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Cupom criado.")
            return redirect("painel:cupom_lista")
    else:
        form = CupomForm()
    return render(request, "painel/cupom_form.html", {"form": form, "titulo_pagina": "Novo cupom"})


@staff_member_required
def cupom_editar(request, pk):
    cupom = get_object_or_404(Cupom, pk=pk)
    if request.method == "POST":
        form = CupomForm(request.POST, instance=cupom)
        if form.is_valid():
            form.save()
            messages.success(request, "Cupom atualizado.")
            return redirect("painel:cupom_lista")
    else:
        form = CupomForm(instance=cupom)
    return render(request, "painel/cupom_form.html", {"form": form, "titulo_pagina": f"Editar — {cupom.codigo}"})


@staff_member_required
def cupom_excluir(request, pk):
    cupom = get_object_or_404(Cupom, pk=pk)
    if request.method == "POST":
        cupom.delete()
        messages.success(request, "Cupom excluído.")
        return redirect("painel:cupom_lista")
    return render(request, "painel/confirmar_exclusao.html", {"objeto": cupom, "voltar_url": "painel:cupom_lista", "voltar_pk": None})


# --- Pergunta frequente (FAQ) ----------------------------------------------

# --- Alunos ------------------------------------------------------------------

@staff_member_required
def alunos_lista(request):
    q = (request.GET.get("q") or "").strip()
    alunos = (
        User.objects.filter(is_staff=False)
        .select_related("perfil")
        .annotate(total_matriculas=Count("matriculas", distinct=True))
        .order_by("-date_joined")
    )
    if q:
        alunos = alunos.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q)
            | Q(username__icontains=q) | Q(email__icontains=q)
            | Q(perfil__telefone__icontains=q) | Q(perfil__cpf__icontains=q)
        )
    return render(request, "painel/alunos_lista.html", {"alunos": alunos, "q": q})


@staff_member_required
def aluno_novo(request):
    """Matricula um aluno manualmente (ex: pagamento combinado fora do site).
    Se já existir conta com esse email, só adiciona os cursos novos — não mexe
    em senha nem dados de quem já tem conta."""
    if request.method == "POST":
        form = MatricularAlunoForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            nome = form.cleaned_data["nome"]
            cursos = form.cleaned_data["cursos"]

            aluno = User.objects.filter(username__iexact=email, is_staff=False).first()
            conta_criada_agora = False
            senha_temporaria = None

            if not aluno:
                senha_temporaria = secrets.token_urlsafe(9)
                aluno = User.objects.create_user(username=email, email=email, first_name=nome)
                aluno.set_password(senha_temporaria)
                aluno.save()
                Perfil.objects.create(
                    user=aluno, telefone=form.cleaned_data["telefone"], cpf=form.cleaned_data["cpf"],
                    deve_trocar_senha=True,
                )
                conta_criada_agora = True

            notificacao = NotificationService()
            cursos_novos = []
            for curso in cursos:
                _, criada = Matricula.objects.get_or_create(aluno=aluno, curso=curso, defaults={"ativo": True})
                if criada:
                    cursos_novos.append(curso)

            for curso in cursos_novos:
                try:
                    notificacao.notificar_matricula(aluno, curso)
                except Exception:
                    logger.exception("Falha ao notificar matrícula manual pra %s (curso %s)", aluno.username, curso.pk)

            if conta_criada_agora:
                try:
                    notificacao.notificar_credenciais(aluno, senha_temporaria)
                except Exception:
                    logger.exception("Falha ao enviar credenciais pra %s", aluno.username)

                modo_mock = ConfiguracaoNotificacao.obter().backend == ConfiguracaoNotificacao.Backend.MOCK
                if modo_mock:
                    messages.success(
                        request,
                        f"Aluno cadastrado e matriculado em {len(cursos_novos)} curso(s). "
                        f"Login: {aluno.username} — Senha temporária: {senha_temporaria}",
                    )
                else:
                    messages.success(request, f"Aluno cadastrado, matriculado em {len(cursos_novos)} curso(s) e credenciais enviadas por email.")
            else:
                messages.success(request, f"{len(cursos_novos)} curso(s) novo(s) adicionado(s) à conta existente de {aluno.get_full_name() or aluno.username}.")

            return redirect("painel:aluno_detalhe", pk=aluno.pk)
    else:
        form = MatricularAlunoForm()

    return render(request, "painel/aluno_novo.html", {"form": form})


@staff_member_required
def aluno_detalhe(request, pk):
    aluno = get_object_or_404(User.objects.select_related("perfil"), pk=pk, is_staff=False)

    matriculas = aluno.matriculas.select_related("curso").all()
    cursos_info = [
        {"matricula": m, "curso": m.curso, "progresso": calcular_progresso(aluno, m.curso)}
        for m in matriculas
    ]

    aulas_concluidas = (
        aluno.aulas_concluidas
        .select_related("aula", "aula__modulo", "aula__modulo__curso")
        .all()[:50]
    )
    pagamentos = Pagamento.objects.filter(aluno=aluno).select_related("curso", "cupom").order_by("-criado_em")
    certificados = Certificado.objects.filter(aluno=aluno).select_related("curso")

    return render(request, "painel/aluno_detalhe.html", {
        "aluno": aluno,
        "perfil": getattr(aluno, "perfil", None),
        "cursos_info": cursos_info,
        "aulas_concluidas": aulas_concluidas,
        "total_aulas_concluidas": aluno.aulas_concluidas.count(),
        "pagamentos": pagamentos,
        "certificados": certificados,
    })


@staff_member_required
def aluno_editar(request, pk):
    aluno = get_object_or_404(User, pk=pk, is_staff=False)
    perfil = getattr(aluno, "perfil", None)

    if request.method == "POST":
        form = AlunoEditForm(request.POST, aluno=aluno)
        if form.is_valid():
            aluno.first_name = form.cleaned_data["nome"]
            aluno.email = form.cleaned_data["email"]
            aluno.username = form.cleaned_data["email"]
            aluno.save(update_fields=["first_name", "email", "username"])
            Perfil.objects.update_or_create(
                user=aluno,
                defaults={"telefone": form.cleaned_data["telefone"], "cpf": form.cleaned_data["cpf"]},
            )
            messages.success(request, "Dados do aluno atualizados.")
            return redirect("painel:aluno_detalhe", pk=aluno.pk)
    else:
        form = AlunoEditForm(aluno=aluno, initial={
            "nome": aluno.first_name,
            "email": aluno.email or aluno.username,
            "telefone": perfil.telefone if perfil else "",
            "cpf": perfil.cpf if perfil else "",
        })

    return render(request, "painel/aluno_editar.html", {"form": form, "aluno": aluno})


@staff_member_required
@require_POST
def aluno_resetar_senha(request, pk):
    aluno = get_object_or_404(User, pk=pk, is_staff=False)

    senha_temporaria = secrets.token_urlsafe(9)
    aluno.set_password(senha_temporaria)
    aluno.save(update_fields=["password"])

    perfil = getattr(aluno, "perfil", None)
    if perfil:
        perfil.deve_trocar_senha = True
        perfil.save(update_fields=["deve_trocar_senha"])

    email_ok = False
    try:
        NotificationService().notificar_credenciais(aluno, senha_temporaria)
        email_ok = True
    except Exception:
        pass

    if email_ok:
        messages.success(
            request,
            f"Senha resetada. Nova senha temporária: {senha_temporaria} — "
            f"também enviada por email para {aluno.email or 'o aluno'}.",
        )
    else:
        messages.warning(
            request,
            f"Senha resetada para: {senha_temporaria} — anote e repasse ao aluno "
            "(o email não foi enviado; verifique a configuração de notificações).",
        )
    return redirect("painel:aluno_detalhe", pk=aluno.pk)


@staff_member_required
@require_POST
def aluno_toggle_ativo(request, pk):
    aluno = get_object_or_404(User, pk=pk, is_staff=False)
    aluno.is_active = not aluno.is_active
    aluno.save(update_fields=["is_active"])
    if aluno.is_active:
        messages.success(request, f"Aluno {aluno.get_full_name() or aluno.get_username()} reativado — pode fazer login novamente.")
    else:
        messages.warning(request, f"Aluno {aluno.get_full_name() or aluno.get_username()} inativado — não consegue mais fazer login. Os dados foram preservados.")
    return redirect("painel:aluno_detalhe", pk=aluno.pk)


# --- Comunicado (email em massa) ---------------------------------------------

@staff_member_required
def comunicado(request):
    cursos = Curso.objects.order_by("titulo")
    turmas = Turma.objects.select_related("curso").order_by("-data_inicio")

    if request.method == "POST":
        destino = request.POST.get("destino", "todos")
        curso_id = request.POST.get("curso") or ""
        turma_id = request.POST.get("turma") or ""
        assunto = (request.POST.get("assunto") or "").strip()
        mensagem = (request.POST.get("mensagem") or "").strip()
        confirmado = request.POST.get("confirmado") == "1"

        curso = None
        turma = None
        erros = []
        if not assunto:
            erros.append("Preencha o assunto.")
        if not mensagem:
            erros.append("Preencha a mensagem.")
        if destino == "curso":
            curso = cursos.filter(pk=curso_id).first() if curso_id.isdigit() else None
            if not curso:
                erros.append("Escolha um curso válido.")
        elif destino == "turma":
            turma = turmas.filter(pk=turma_id).first() if turma_id.isdigit() else None
            if not turma:
                erros.append("Escolha uma turma válida.")

        if destino == "curso" and curso:
            alunos = User.objects.filter(
                is_active=True, is_staff=False,
                matriculas__curso=curso, matriculas__ativo=True,
            ).distinct()
        elif destino == "turma" and turma:
            alunos = User.objects.filter(
                is_active=True, is_staff=False,
                inscricoes_turma__turma=turma,
            ).distinct()
        else:
            alunos = User.objects.filter(is_active=True, is_staff=False)
        total = alunos.count()

        contexto = {
            "cursos": cursos, "turmas": turmas, "destino": destino, "curso_id": curso_id, "turma_id": turma_id,
            "assunto": assunto, "mensagem": mensagem, "erros": erros, "total": total,
        }

        if erros:
            return render(request, "painel/comunicado_form.html", contexto)

        if not confirmado:
            # passo 1: mostra confirmação com a contagem
            contexto["precisa_confirmar"] = True
            return render(request, "painel/comunicado_form.html", contexto)

        # passo 2: envia
        try:
            enviados = NotificationService().enviar_comunicado(alunos, assunto, mensagem)
            messages.success(request, f"Comunicado enviado para {enviados} aluno(s).")
        except Exception:
            logger.exception("Falha ao enviar comunicado")
            messages.error(request, "Erro ao enviar o comunicado. Verifique a configuração de email.")
        return redirect("painel:comunicado")

    return render(request, "painel/comunicado_form.html", {"cursos": cursos, "turmas": turmas, "destino": "todos"})


# --- Contato -----------------------------------------------------------------

@staff_member_required
def contatos_lista(request):
    mensagens = ContatoMensagem.objects.all().order_by("-enviado_em")
    return render(request, "painel/contatos_lista.html", {"mensagens": mensagens})


@staff_member_required
def faq_lista(request):
    perguntas = PerguntaFrequente.objects.all()
    return render(request, "painel/faq_lista.html", {"perguntas": perguntas})


@staff_member_required
def faq_nova(request):
    if request.method == "POST":
        form = PerguntaFrequenteForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Pergunta criada.")
            return redirect("painel:faq_lista")
    else:
        form = PerguntaFrequenteForm()
    return render(request, "painel/faq_form.html", {"form": form, "titulo_pagina": "Nova pergunta frequente"})


@staff_member_required
def faq_editar(request, pk):
    pergunta = get_object_or_404(PerguntaFrequente, pk=pk)
    if request.method == "POST":
        form = PerguntaFrequenteForm(request.POST, instance=pergunta)
        if form.is_valid():
            form.save()
            messages.success(request, "Pergunta atualizada.")
            return redirect("painel:faq_lista")
    else:
        form = PerguntaFrequenteForm(instance=pergunta)
    return render(request, "painel/faq_form.html", {"form": form, "titulo_pagina": f"Editar — {pergunta.pergunta}"})


@staff_member_required
def faq_excluir(request, pk):
    pergunta = get_object_or_404(PerguntaFrequente, pk=pk)
    if request.method == "POST":
        pergunta.delete()
        messages.success(request, "Pergunta excluída.")
        return redirect("painel:faq_lista")
    return render(request, "painel/confirmar_exclusao.html", {"objeto": pergunta, "voltar_url": "painel:faq_lista", "voltar_pk": None})

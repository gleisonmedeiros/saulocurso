import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from matriculas.mixins import matricula_required_aula, matricula_required_curso
from matriculas.models import AulaConcluida, Certificado, InscricaoTurma, InteresseTurma, Matricula
from matriculas.progresso import calcular_progresso, emitir_certificado_se_completo
from matriculas.turmas import situacao_turma
from notificacoes.services import NotificationService

from .forms import ContatoForm
from .models import ContatoMensagem, Curso, PerguntaFrequente, Turma

logger = logging.getLogger(__name__)


def home(request):
    cursos = Curso.objects.filter(ativo=True)[:8]
    faqs = PerguntaFrequente.objects.filter(ativa=True)
    return render(request, "cursos/home.html", {"cursos": cursos, "faqs": faqs})


def lista_cursos(request):
    cursos = Curso.objects.filter(ativo=True)
    return render(request, "cursos/lista.html", {"cursos": cursos})


def contato(request):
    if request.method == "POST":
        form = ContatoForm(request.POST)
        if form.is_valid():
            contato_mensagem = ContatoMensagem.objects.create(
                tipo=ContatoMensagem.Tipo.CONTATO,
                email=form.cleaned_data["email"],
                telefone=form.cleaned_data["telefone"],
                mensagem=form.cleaned_data["mensagem"],
            )
            try:
                NotificationService().notificar_contato(contato_mensagem)
            except Exception:
                logger.exception("Falha ao notificar contato %s", contato_mensagem.pk)
            messages.success(request, "Mensagem enviada! Vamos retornar em breve.")
            return redirect("cursos:contato")
    else:
        form = ContatoForm()

    return render(request, "cursos/contato.html", {"form": form})


def empresas(request):
    if request.method == "POST":
        form = ContatoForm(request.POST)
        if form.is_valid():
            contato_mensagem = ContatoMensagem.objects.create(
                tipo=ContatoMensagem.Tipo.EMPRESA,
                email=form.cleaned_data["email"],
                telefone=form.cleaned_data["telefone"],
                mensagem=form.cleaned_data["mensagem"],
            )
            try:
                NotificationService().notificar_contato(contato_mensagem)
            except Exception:
                logger.exception("Falha ao notificar contato empresa %s", contato_mensagem.pk)
            messages.success(request, "Pedido de orçamento enviado! Vamos retornar em breve.")
            return redirect("cursos:empresas")
    else:
        form = ContatoForm()

    return render(request, "cursos/empresas.html", {"form": form})


def agenda(request):
    turmas = (
        Turma.objects.filter(curso__ativo=True, data_inicio__gte=timezone.now())
        .select_related("curso")
        .order_by("data_inicio")
    )
    return render(request, "cursos/agenda.html", {"turmas": turmas})


def privacidade(request):
    return render(request, "cursos/privacidade.html")


def detalhe(request, slug):
    curso = get_object_or_404(Curso, slug=slug, ativo=True)
    ja_matriculado = (
        request.user.is_authenticated
        and Matricula.objects.filter(aluno=request.user, curso=curso, ativo=True).exists()
    )
    return render(request, "cursos/detalhe.html", {"curso": curso, "ja_matriculado": ja_matriculado})


@login_required
def minha_area(request):
    matriculas = Matricula.objects.filter(aluno=request.user, ativo=True).select_related("curso")
    for matricula in matriculas:
        matricula.progresso = calcular_progresso(request.user, matricula.curso)
    return render(request, "cursos/minha_area.html", {"matriculas": matriculas})


@login_required
def turma_ingressar(request, turma_id):
    turma = get_object_or_404(Turma, pk=turma_id)
    if request.method != "POST":
        return redirect("cursos:conteudo", slug=turma.curso.slug)

    if not Matricula.objects.filter(aluno=request.user, curso=turma.curso, ativo=True).exists():
        return redirect("cursos:minha_area")

    if not turma.esta_aberta():
        messages.error(request, "Essa turma acabou de ficar sem vaga. Tenta a próxima ou pede aviso.")
        return redirect("cursos:conteudo", slug=turma.curso.slug)

    InscricaoTurma.objects.get_or_create(aluno=request.user, turma=turma)
    try:
        NotificationService().notificar_ingresso_turma(request.user, turma)
    except Exception:
        logger.exception("Falha ao enviar credenciais da turma %s pra %s", turma.pk, request.user.username)

    messages.success(request, "Vaga confirmada! O link do grupo e as informações também foram enviados por email.")
    return redirect("cursos:conteudo", slug=turma.curso.slug)


@login_required
def turma_notificar_interesse(request, curso_id):
    curso = get_object_or_404(Curso, pk=curso_id)
    if request.method != "POST":
        return redirect("cursos:conteudo", slug=curso.slug)

    if not Matricula.objects.filter(aluno=request.user, curso=curso, ativo=True).exists():
        return redirect("cursos:minha_area")

    interesse, criado = InteresseTurma.objects.get_or_create(aluno=request.user, curso=curso)
    if not criado and interesse.notificado_em is not None:
        interesse.notificado_em = None
        interesse.save(update_fields=["notificado_em"])

    messages.success(request, "Combinado! Você recebe um email assim que abrir uma turma nova.")
    return redirect("cursos:conteudo", slug=curso.slug)


@matricula_required_curso
def conteudo(request, slug, curso):
    modulos = curso.modulos.prefetch_related("aulas")
    progresso = calcular_progresso(request.user, curso)
    aulas_concluidas_ids = set(
        AulaConcluida.objects.filter(aluno=request.user, aula__modulo__curso=curso).values_list("aula_id", flat=True)
    )
    certificado = Certificado.objects.filter(aluno=request.user, curso=curso).first()
    mentorias = [m for m in curso.mentorias.all() if m.visivel_para(request.user)]
    return render(
        request,
        "cursos/conteudo.html",
        {
            "curso": curso,
            "modulos": modulos,
            "progresso": progresso,
            "aulas_concluidas_ids": aulas_concluidas_ids,
            "certificado": certificado,
            "mentorias": mentorias,
            "situacao_turma": situacao_turma(request.user, curso),
        },
    )


@matricula_required_aula
def assistir_aula(request, aula_id, aula):
    concluida = AulaConcluida.objects.filter(aluno=request.user, aula=aula).exists()
    return render(request, "cursos/assistir_aula.html", {"aula": aula, "curso": aula.curso, "concluida": concluida})


@matricula_required_aula
def concluir_aula(request, aula_id, aula):
    if request.method != "POST":
        return redirect("cursos:assistir_aula", aula_id=aula.id)

    AulaConcluida.objects.get_or_create(aluno=request.user, aula=aula)
    certificado = emitir_certificado_se_completo(request.user, aula.curso)

    if certificado:
        messages.success(request, "Última aula concluída! Seu certificado já está disponível.")
    else:
        messages.success(request, "Aula marcada como concluída.")

    return redirect("cursos:conteudo", slug=aula.curso.slug)


@matricula_required_curso
def certificado(request, slug, curso):
    cert = Certificado.objects.filter(aluno=request.user, curso=curso).first()
    if not cert:
        messages.error(request, "Você ainda não concluiu todas as aulas deste curso.")
        return redirect("cursos:conteudo", slug=curso.slug)

    return render(request, "cursos/certificado.html", {"curso": curso, "certificado": cert})


@matricula_required_aula
def aula_video_token(request, aula_id, aula):
    if aula.drive_file_id:
        return JsonResponse({"fonte": "drive", "video_id": aula.drive_file_id})
    if aula.youtube_id:
        return JsonResponse({"fonte": "youtube", "video_id": aula.youtube_id})
    return JsonResponse({"error": "esta aula não tem vídeo"}, status=404)


@matricula_required_aula
def aula_pdf_token(request, aula_id, aula):
    if aula.drive_pdf_file_id:
        return JsonResponse({"fonte": "drive", "file_id": aula.drive_pdf_file_id})
    return JsonResponse({"error": "esta aula não tem apostila"}, status=404)

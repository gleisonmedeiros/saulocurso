from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms_painel import (
    AulaForm, ConfiguracaoSiteForm, CursoForm, MentoriaForm, ModuloForm, PerguntaFrequenteForm, TurmaForm,
)
from .models import Aula, ConfiguracaoSite, Curso, MentoriaAoVivo, Modulo, PerguntaFrequente, Turma


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


# --- Curso -----------------------------------------------------------------

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
            form.save()
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


# --- Pergunta frequente (FAQ) ----------------------------------------------

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

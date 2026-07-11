from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from cursos.models import Aula, Curso

from .models import Matricula


def tem_matricula_ativa(user, curso):
    if not user.is_authenticated:
        return False
    return Matricula.objects.filter(aluno=user, curso=curso, ativo=True).exists()


def matricula_required_curso(view_func):
    """Exige login + matrícula ativa no curso identificado pelo kwarg 'slug' da URL."""

    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        curso = get_object_or_404(Curso, slug=kwargs["slug"])
        if not tem_matricula_ativa(request.user, curso):
            raise PermissionDenied("Você não está matriculado neste curso.")
        return view_func(request, *args, curso=curso, **kwargs)

    return wrapper


def matricula_required_aula(view_func):
    """Exige login + matrícula ativa no curso da aula identificada pelo kwarg 'aula_id' da URL."""

    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        aula = get_object_or_404(Aula, pk=kwargs["aula_id"])
        if not tem_matricula_ativa(request.user, aula.curso):
            raise PermissionDenied("Você não está matriculado neste curso.")
        return view_func(request, *args, aula=aula, **kwargs)

    return wrapper

from django.utils import timezone

from cursos.models import Turma

from .models import InscricaoTurma, InteresseTurma


def situacao_turma(aluno, curso):
    """Estado da turma pro aluno matriculado nesse curso, pro bloco de
    ingresso do Portal do Aluno:
    - "inscrito": já ingressou numa turma futura desse curso.
    - "aberta": tem turma futura com vaga — pode ingressar.
    - "esgotada": nenhuma turma futura com vaga — mostra próximas (se houver)
      e se já pediu (ou pode pedir) aviso quando abrir."""
    hoje = timezone.now()
    turmas_futuras = list(Turma.objects.filter(curso=curso, data_inicio__gte=hoje).order_by("data_inicio"))

    inscricao = (
        InscricaoTurma.objects.filter(aluno=aluno, turma__curso=curso, turma__data_inicio__gte=hoje)
        .select_related("turma").first()
    )
    if inscricao:
        return {"estado": "inscrito", "turma": inscricao.turma}

    turma_aberta = next((t for t in turmas_futuras if t.esta_aberta()), None)
    if turma_aberta:
        return {"estado": "aberta", "turma": turma_aberta}

    interesse_registrado = InteresseTurma.objects.filter(
        aluno=aluno, curso=curso, notificado_em__isnull=True,
    ).exists()
    return {
        "estado": "esgotada",
        "proximas_turmas": turmas_futuras[:3],
        "interesse_registrado": interesse_registrado,
    }

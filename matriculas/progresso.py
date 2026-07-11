from cursos.models import Aula

from .models import AulaConcluida, Certificado


def calcular_progresso(aluno, curso):
    total = Aula.objects.filter(modulo__curso=curso).count()
    concluidas = AulaConcluida.objects.filter(aluno=aluno, aula__modulo__curso=curso).count()
    percentual = round((concluidas / total) * 100) if total else 0
    return {"concluidas": concluidas, "total": total, "percentual": percentual, "completo": total > 0 and concluidas >= total}


def emitir_certificado_se_completo(aluno, curso):
    progresso = calcular_progresso(aluno, curso)
    if not progresso["completo"]:
        return None
    certificado, _ = Certificado.objects.get_or_create(aluno=aluno, curso=curso)
    return certificado

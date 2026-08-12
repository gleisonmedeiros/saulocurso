import uuid

from django.conf import settings
from django.db import models


class Matricula(models.Model):
    aluno = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="matriculas")
    curso = models.ForeignKey("cursos.Curso", on_delete=models.CASCADE, related_name="matriculas")
    ativo = models.BooleanField(default=True)
    data_matricula = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("aluno", "curso")
        ordering = ["-data_matricula"]

    def __str__(self):
        return f"{self.aluno.get_username()} — {self.curso.titulo}"


class AulaConcluida(models.Model):
    aluno = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="aulas_concluidas")
    aula = models.ForeignKey("cursos.Aula", on_delete=models.CASCADE, related_name="conclusoes")
    concluida_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("aluno", "aula")
        ordering = ["-concluida_em"]

    def __str__(self):
        return f"{self.aluno.get_username()} concluiu {self.aula.titulo}"


class Certificado(models.Model):
    aluno = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="certificados")
    curso = models.ForeignKey("cursos.Curso", on_delete=models.CASCADE, related_name="certificados")
    codigo = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    emitido_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("aluno", "curso")
        ordering = ["-emitido_em"]

    def __str__(self):
        return f"Certificado — {self.aluno.get_username()} — {self.curso.titulo}"


class InscricaoTurma(models.Model):
    """Aluno confirmou presença numa turma específica — dispara o envio do
    link do grupo/informações de acesso e conta contra o limite de vagas."""

    aluno = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="inscricoes_turma")
    turma = models.ForeignKey("cursos.Turma", on_delete=models.CASCADE, related_name="inscricoes")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("aluno", "turma")
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.aluno.get_username()} — {self.turma}"


class InteresseTurma(models.Model):
    """Aluno pediu aviso quando abrir turma nova pro curso (turma atual
    esgotada ou nenhuma agendada). notificado_em marca quando já avisamos —
    fica None de novo se o aluno pedir aviso outra vez depois."""

    aluno = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="interesses_turma")
    curso = models.ForeignKey("cursos.Curso", on_delete=models.CASCADE, related_name="interesses_turma")
    criado_em = models.DateTimeField(auto_now_add=True)
    notificado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("aluno", "curso")
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.aluno.get_username()} — {self.curso.titulo} (interesse)"

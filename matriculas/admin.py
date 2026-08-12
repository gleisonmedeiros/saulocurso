from django.contrib import admin

from .models import AulaConcluida, Certificado, InscricaoTurma, InteresseTurma, Matricula


@admin.register(Matricula)
class MatriculaAdmin(admin.ModelAdmin):
    list_display = ("aluno", "curso", "ativo", "data_matricula")
    list_filter = ("ativo", "curso")
    search_fields = ("aluno__username", "curso__titulo")


@admin.register(AulaConcluida)
class AulaConcluidaAdmin(admin.ModelAdmin):
    list_display = ("aluno", "aula", "concluida_em")
    list_filter = ("aula__modulo__curso",)
    search_fields = ("aluno__username", "aula__titulo")

    def has_add_permission(self, request):
        return False


@admin.register(Certificado)
class CertificadoAdmin(admin.ModelAdmin):
    list_display = ("aluno", "curso", "codigo", "emitido_em")
    list_filter = ("curso",)
    search_fields = ("aluno__username", "curso__titulo", "codigo")

    def has_add_permission(self, request):
        return False


@admin.register(InscricaoTurma)
class InscricaoTurmaAdmin(admin.ModelAdmin):
    list_display = ("aluno", "turma", "criado_em")
    list_filter = ("turma__curso",)
    search_fields = ("aluno__username", "turma__curso__titulo")


@admin.register(InteresseTurma)
class InteresseTurmaAdmin(admin.ModelAdmin):
    list_display = ("aluno", "curso", "criado_em", "notificado_em")
    list_filter = ("curso",)
    search_fields = ("aluno__username", "curso__titulo")

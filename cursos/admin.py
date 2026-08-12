from django.contrib import admin

from .models import Aula, ContatoMensagem, Cupom, Curso, MentoriaAoVivo, Modulo, PerguntaFrequente, Turma


class AulaInline(admin.TabularInline):
    model = Aula
    extra = 1
    fields = ("titulo", "youtube_id", "drive_file_id", "drive_pdf_file_id", "ordem")


class ModuloInline(admin.StackedInline):
    model = Modulo
    extra = 1
    fields = ("titulo", "ordem")
    show_change_link = True


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "preco", "carga_horaria", "modalidade", "ativo", "criado_em")
    list_filter = ("ativo", "modalidade")
    search_fields = ("titulo", "descricao_curta")
    prepopulated_fields = {"slug": ("titulo",)}
    inlines = [ModuloInline]


@admin.register(Modulo)
class ModuloAdmin(admin.ModelAdmin):
    list_display = ("titulo", "curso", "ordem")
    list_filter = ("curso",)
    inlines = [AulaInline]


@admin.register(Aula)
class AulaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "modulo", "youtube_id", "drive_file_id", "drive_pdf_file_id", "ordem")
    list_filter = ("modulo__curso",)


@admin.register(MentoriaAoVivo)
class MentoriaAoVivoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "curso", "data_hora")
    list_filter = ("curso",)


@admin.register(Turma)
class TurmaAdmin(admin.ModelAdmin):
    list_display = ("curso", "data_inicio", "vagas")
    list_filter = ("curso",)


@admin.register(PerguntaFrequente)
class PerguntaFrequenteAdmin(admin.ModelAdmin):
    list_display = ("pergunta", "ordem", "ativa")
    list_editable = ("ordem", "ativa")


@admin.register(Cupom)
class CupomAdmin(admin.ModelAdmin):
    list_display = ("codigo", "tipo", "percentual_desconto", "validade", "ativo")
    list_filter = ("tipo", "ativo")
    search_fields = ("codigo",)
    filter_horizontal = ("cursos",)


@admin.register(ContatoMensagem)
class ContatoMensagemAdmin(admin.ModelAdmin):
    list_display = ("email", "telefone", "tipo", "enviado_em")
    list_filter = ("tipo",)
    search_fields = ("email", "telefone", "mensagem")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

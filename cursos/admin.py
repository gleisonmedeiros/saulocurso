from django.contrib import admin

from .models import Aula, ContatoMensagem, Curso, MentoriaAoVivo, Modulo


class AulaInline(admin.TabularInline):
    model = Aula
    extra = 1
    fields = ("titulo", "youtube_id", "drive_file_id", "arquivo_pdf", "ordem")


class ModuloInline(admin.StackedInline):
    model = Modulo
    extra = 1
    fields = ("titulo", "ordem")
    show_change_link = True


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "preco", "ativo", "criado_em")
    list_filter = ("ativo",)
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
    list_display = ("titulo", "modulo", "youtube_id", "drive_file_id", "arquivo_pdf", "ordem")
    list_filter = ("modulo__curso",)


@admin.register(MentoriaAoVivo)
class MentoriaAoVivoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "curso", "data_hora")
    list_filter = ("curso",)


@admin.register(ContatoMensagem)
class ContatoMensagemAdmin(admin.ModelAdmin):
    list_display = ("email", "telefone", "enviado_em")
    search_fields = ("email", "telefone", "mensagem")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

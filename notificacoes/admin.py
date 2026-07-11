from django.contrib import admin

from .models import NotificacaoLog


@admin.register(NotificacaoLog)
class NotificacaoLogAdmin(admin.ModelAdmin):
    list_display = ("canal", "destinatario", "assunto", "enviado_em")
    list_filter = ("canal",)
    search_fields = ("destinatario", "assunto", "mensagem")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

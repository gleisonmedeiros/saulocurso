from django.contrib import admin

from .models import CobrancaExterna, Pagamento


@admin.register(Pagamento)
class PagamentoAdmin(admin.ModelAdmin):
    list_display = ("aluno", "curso", "valor", "status", "metodo", "criado_em")
    list_filter = ("status", "metodo")
    search_fields = ("aluno__username", "curso__titulo")


@admin.register(CobrancaExterna)
class CobrancaExternaAdmin(admin.ModelAdmin):
    list_display = ("order_nsu", "pagamento", "confirmado", "criado_em", "confirmado_em")
    list_filter = ("confirmado",)
    search_fields = ("order_nsu", "transaction_nsu", "pagamento__aluno__username", "pagamento__curso__titulo")
    readonly_fields = ("criado_em", "confirmado_em")

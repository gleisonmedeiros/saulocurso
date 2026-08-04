from django.urls import path

from . import views_painel as views

app_name = "painel"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("configuracoes/", views.configuracoes, name="configuracoes"),
    path("pagamento/", views.pagamento_config, name="pagamento_config"),
    path("notificacoes/", views.notificacoes_config, name="notificacoes_config"),

    path("cursos/novo/", views.curso_novo, name="curso_novo"),
    path("cursos/<int:pk>/", views.curso_detalhe, name="curso_detalhe"),
    path("cursos/<int:pk>/editar/", views.curso_editar, name="curso_editar"),
    path("cursos/<int:pk>/excluir/", views.curso_excluir, name="curso_excluir"),

    path("cursos/<int:curso_pk>/modulos/novo/", views.modulo_novo, name="modulo_novo"),
    path("modulos/<int:pk>/editar/", views.modulo_editar, name="modulo_editar"),
    path("modulos/<int:pk>/excluir/", views.modulo_excluir, name="modulo_excluir"),

    path("modulos/<int:modulo_pk>/aulas/novo/", views.aula_nova, name="aula_nova"),
    path("aulas/<int:pk>/editar/", views.aula_editar, name="aula_editar"),
    path("aulas/<int:pk>/excluir/", views.aula_excluir, name="aula_excluir"),

    path("cursos/<int:curso_pk>/mentorias/novo/", views.mentoria_nova, name="mentoria_nova"),
    path("mentorias/<int:pk>/editar/", views.mentoria_editar, name="mentoria_editar"),
    path("mentorias/<int:pk>/excluir/", views.mentoria_excluir, name="mentoria_excluir"),

    path("cursos/<int:curso_pk>/turmas/novo/", views.turma_nova, name="turma_nova"),
    path("turmas/<int:pk>/editar/", views.turma_editar, name="turma_editar"),
    path("turmas/<int:pk>/excluir/", views.turma_excluir, name="turma_excluir"),

    path("faq/", views.faq_lista, name="faq_lista"),
    path("faq/novo/", views.faq_nova, name="faq_nova"),
    path("faq/<int:pk>/editar/", views.faq_editar, name="faq_editar"),
    path("faq/<int:pk>/excluir/", views.faq_excluir, name="faq_excluir"),
]

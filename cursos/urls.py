from django.urls import path

from . import views

app_name = "cursos"

urlpatterns = [
    path("", views.home, name="home"),
    path("contato/", views.contato, name="contato"),
    path("empresas/", views.empresas, name="empresas"),
    path("agenda/", views.agenda, name="agenda"),
    path("privacidade/", views.privacidade, name="privacidade"),
    path("minha-area/", views.minha_area, name="minha_area"),
    path("turmas/<int:turma_id>/ingressar/", views.turma_ingressar, name="turma_ingressar"),
    path("cursos/<int:curso_id>/turma-interesse/", views.turma_notificar_interesse, name="turma_notificar_interesse"),
    path("cursos/", views.lista_cursos, name="lista"),
    path("cursos/<slug:slug>/", views.detalhe, name="detalhe"),
    path("cursos/<slug:slug>/conteudo/", views.conteudo, name="conteudo"),
    path("cursos/<slug:slug>/certificado/", views.certificado, name="certificado"),
    path("aulas/<int:aula_id>/", views.assistir_aula, name="assistir_aula"),
    path("aulas/<int:aula_id>/video-token/", views.aula_video_token, name="aula_video_token"),
    path("aulas/<int:aula_id>/pdf-token/", views.aula_pdf_token, name="aula_pdf_token"),
    path("aulas/<int:aula_id>/concluir/", views.concluir_aula, name="concluir_aula"),
]

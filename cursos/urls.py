from django.urls import path

from . import views

app_name = "cursos"

urlpatterns = [
    path("", views.home, name="home"),
    path("contato/", views.contato, name="contato"),
    path("minha-area/", views.minha_area, name="minha_area"),
    path("cursos/", views.lista_cursos, name="lista"),
    path("cursos/<slug:slug>/", views.detalhe, name="detalhe"),
    path("cursos/<slug:slug>/conteudo/", views.conteudo, name="conteudo"),
    path("cursos/<slug:slug>/certificado/", views.certificado, name="certificado"),
    path("certificados/<uuid:codigo>/verificar/", views.verificar_certificado, name="verificar_certificado"),
    path("certificados/<uuid:codigo>/qrcode/", views.certificado_qrcode, name="certificado_qrcode"),
    path("aulas/<int:aula_id>/", views.assistir_aula, name="assistir_aula"),
    path("aulas/<int:aula_id>/video-token/", views.aula_video_token, name="aula_video_token"),
    path("aulas/<int:aula_id>/pdf/", views.aula_pdf, name="aula_pdf"),
    path("aulas/<int:aula_id>/pdf-token/", views.aula_pdf_token, name="aula_pdf_token"),
    path("aulas/<int:aula_id>/concluir/", views.concluir_aula, name="concluir_aula"),
]

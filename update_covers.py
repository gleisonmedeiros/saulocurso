import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from cursos.models import Curso

updates = {
    13: '/static/img/cursos/bls.jpg',
    14: '/static/img/cursos/stop_the_bleed.jpg',
    15: '/static/img/cursos/mascara_laringea.jpg',
    16: '/static/img/cursos/urgencia_emergencia.jpg',
    17: '/static/img/cursos/lei_lucas.jpg',
}

for pk, url in updates.items():
    try:
        curso = Curso.objects.get(pk=pk)
        curso.capa_url_externa = url
        curso.save()
        print(f"Updated {curso.titulo} with {url}")
    except Curso.DoesNotExist:
        print(f"Course pk={pk} not found")

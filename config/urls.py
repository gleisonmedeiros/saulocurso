from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Saulo Curso — Administração"
admin.site.site_title = "Saulo Curso Admin"
admin.site.index_title = "Painel de controle"

urlpatterns = [
    path('admin/', admin.site.urls),
    path('painel/', include('cursos.urls_painel')),
    path('accounts/', include('accounts.urls')),
    path('pagamentos/', include('pagamentos.urls')),
    path('', include('cursos.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

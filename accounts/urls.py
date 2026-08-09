from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import LoginForm

app_name = "accounts"

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="accounts/login.html", authentication_form=LoginForm), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("trocar-senha/", views.trocar_senha, name="trocar_senha"),

    path("esqueci-senha/", views.esqueci_senha, name="esqueci_senha"),
    path("esqueci-senha/codigo/", views.verificar_codigo, name="verificar_codigo"),
    path("esqueci-senha/nova/", views.redefinir_senha, name="redefinir_senha"),
]

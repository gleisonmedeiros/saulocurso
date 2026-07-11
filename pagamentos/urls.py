from django.urls import path

from . import views

app_name = "pagamentos"

urlpatterns = [
    path("checkout/<slug:slug>/", views.checkout, name="checkout"),
    path("cadastro/", views.cadastro_pos_pagamento, name="cadastro"),
]

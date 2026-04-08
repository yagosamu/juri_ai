from django.urls import path
from . import views

urlpatterns = [
    path('cadastro/', views.cadastro, name='cadastro'),
    path("login/", views.login, name='login'),
    path("dashboard/", views.dashboard, name='dashboard'),
    path("clientes/", views.clientes, name='clientes'),
    path("cliente/<int:id>", views.cliente, name='cliente'),
    # ── Processos ─────────────────────────────────────────────────────────────
    path("processos/", views.lista_processos, name='lista_processos'),
    path("processos/novo/", views.criar_processo, name='criar_processo'),
    path("processos/<int:id>/", views.processo, name='processo'),
    path("processos/<int:id>/editar/", views.editar_processo, name='editar_processo'),
    path("processos/<int:id>/arquivar/", views.arquivar_processo, name='arquivar_processo'),
    path("processos/<int:id>/vincular-documento/", views.vincular_documento, name='vincular_documento'),
    # ─────────────────────────────────────────────────────────────────────────
    path("configuracao_whatsapp/", views.configuracao_whatsapp, name='configuracao_whatsapp'),
    path("logout/", views.logout, name='logout'),
    path("excluir-conta/", views.excluir_conta, name='excluir_conta'),
]
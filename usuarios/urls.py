from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('cadastro/', views.cadastro, name='cadastro'),
    path("login/", views.login, name='login'),
    path('password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
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
    path("processos/<int:id>/atualizar-datajud/", views.atualizar_datajud, name='atualizar_datajud'),
    # ── Prazos ────────────────────────────────────────────────────────────────
    path("prazos/", views.lista_prazos, name='lista_prazos'),
    path("processos/<int:processo_id>/prazos/novo/", views.criar_prazo, name='criar_prazo'),
    path("prazos/<int:id>/editar/", views.editar_prazo, name='editar_prazo'),
    path("prazos/<int:id>/concluir/", views.concluir_prazo, name='concluir_prazo'),
    path("prazos/<int:id>/cancelar/", views.cancelar_prazo, name='cancelar_prazo'),
    # ── Financeiro ───────────────────────────────────────────────────────────
    path("financeiro/", views.lista_financeiro, name='lista_financeiro'),
    path("financeiro/honorario/novo/", views.criar_honorario, name='criar_honorario'),
    path("financeiro/honorario/<int:id>/editar/", views.editar_honorario, name='editar_honorario'),
    path("financeiro/honorario/<int:id>/pagar/", views.marcar_pago, name='marcar_pago'),
    path("financeiro/honorario/<int:id>/cancelar/", views.cancelar_honorario, name='cancelar_honorario'),
    path("financeiro/relatorio/", views.relatorio_financeiro, name='relatorio_financeiro'),
    # ── Templates de Documentos ──────────────────────────────────────────────
    path("templates/",                  views.lista_templates,  name='lista_templates'),
    path("templates/novo/",             views.criar_template,   name='criar_template'),
    path("templates/<int:id>/editar/",  views.editar_template,  name='editar_template'),
    path("templates/<int:id>/deletar/", views.deletar_template, name='deletar_template'),
    # ─────────────────────────────────────────────────────────────────────────
    path("configuracao_whatsapp/", views.configuracao_whatsapp, name='configuracao_whatsapp'),
    path("logout/", views.logout, name='logout'),
    path("excluir-conta/", views.excluir_conta, name='excluir_conta'),
]
from django.urls import path
from . import views

urlpatterns = [
    path('cadastro/', views.cadastro, name='cadastro'),
    path("login/", views.login, name='login'),
    path("dashboard/", views.dashboard, name='dashboard'),
    path("clientes/", views.clientes, name='clientes'),
    path("cliente/<int:id>", views.cliente, name='cliente'),
    path("configuracao_whatsapp/", views.configuracao_whatsapp, name='configuracao_whatsapp'),
    path("logout/", views.logout, name='logout'),
]
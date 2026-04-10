from django.urls import path
from . import views

urlpatterns = [
    path("chat/<int:id>", views.chat, name='chat'),
    path("stream_response/", views.stream_resposta, name='stream_resposta'),
    path("ver_referencias/<int:id>", views.ver_referencias, name='ver_referencias'),
    path("analise_jurisprudencia/<int:id>", views.analise_jurisprudencia, name='analise_jurisprudencia'),
    path("processar_analise/<int:id>", views.processar_analise, name='processar_analise'),
    path("webhook_whatsapp/", views.webhook_whatsapp, name='webhook_whatsapp'),
    path("chats/",    views.lista_chats,    name='lista_chats'),
    path("analises/", views.lista_analises, name='lista_analises'),
    # ── Geração de Documentos ────────────────────────────────────────────────
    path("documentos/gerar/",             views.gerar_documento,    name='gerar_documento'),
    path("documentos/salvar/",            views.salvar_documento,   name='salvar_documento'),
    path("documentos/<int:id>/editar/",   views.editar_documento,   name='editar_documento'),
    path("documentos/<int:id>/exportar/", views.exportar_documento, name='exportar_documento'),
    path("documentos/<int:id>/vincular/", views.vincular_doc_gerado, name='vincular_doc_gerado'),
]
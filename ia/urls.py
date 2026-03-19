from django.urls import path
from . import views

urlpatterns = [
    path("chat/<int:id>", views.chat, name='chat'),
    path("stream_response/", views.stream_resposta, name='stream_resposta'),
    path("ver_referencias/<int:id>", views.ver_referencias, name='ver_referencias'),
]
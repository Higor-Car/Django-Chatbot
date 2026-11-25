from django.urls import path

from . import views

app_name = 'chatbot'

urlpatterns = [
    path('', views.chat, name='inicio'),
    path('conversas/nova/', views.nova_conversa, name='nova_conversa'),
    path('conversas/<int:conversa_id>/', views.chat, name='conversa'),
    path('conversas/<int:conversa_id>/enviar/', views.enviar_mensagem, name='enviar_mensagem'),
    path('conversas/<int:conversa_id>/excluir/', views.excluir_conversa, name='excluir_conversa'),
    path('conversas/<int:conversa_id>/renomear/', views.renomear_conversa, name='renomear_conversa'),
]

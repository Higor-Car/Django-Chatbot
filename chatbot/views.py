from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Conversa, Mensagem
from .ollama import OllamaError, gerar_resposta

TAMANHO_MAXIMO_MENSAGEM = 4000


def chat(request, conversa_id=None):
    conversa = get_object_or_404(Conversa, pk=conversa_id) if conversa_id else None
    return render(request, 'chatbot/chat.html', {
        'conversas': Conversa.objects.all(),
        'conversa': conversa,
        'mensagens': conversa.mensagens.all() if conversa else [],
        'modelo': settings.OLLAMA_MODEL,
    })


@require_POST
def nova_conversa(request):
    return redirect('chatbot:conversa', conversa_id=Conversa.objects.create().pk)


def _quer_json(request):
    return 'application/json' in request.headers.get('Accept', '')


@require_POST
def excluir_conversa(request, conversa_id):
    get_object_or_404(Conversa, pk=conversa_id).delete()
    if _quer_json(request):
        return JsonResponse({'ok': True})
    return redirect('chatbot:inicio')


@require_POST
def renomear_conversa(request, conversa_id):
    conversa = get_object_or_404(Conversa, pk=conversa_id)
    titulo = request.POST.get('titulo', '').strip()
    if not titulo:
        return JsonResponse({'erro': 'O nome não pode ficar vazio.'}, status=400)
    conversa.titulo = titulo[:100]
    conversa.save(update_fields=['titulo'])  # renomear não deve mudar a ordem da lista
    return JsonResponse({'titulo': conversa.titulo})


@require_POST
def enviar_mensagem(request, conversa_id):
    conversa = get_object_or_404(Conversa, pk=conversa_id)
    texto = request.POST.get('mensagem', '').strip()

    if not texto:
        return JsonResponse({'erro': 'Digite uma mensagem.'}, status=400)
    if len(texto) > TAMANHO_MAXIMO_MENSAGEM:
        return JsonResponse(
            {'erro': f'A mensagem pode ter no máximo {TAMANHO_MAXIMO_MENSAGEM} caracteres.'},
            status=400,
        )

    # Últimas mensagens da conversa como contexto, na ordem cronológica.
    anteriores = list(conversa.mensagens.order_by('-criada_em', '-id')[:settings.CHATBOT_HISTORY_LIMIT])
    historico = [{'role': m.papel, 'content': m.conteudo} for m in reversed(anteriores)]
    historico.append({'role': 'user', 'content': texto})

    try:
        resposta = gerar_resposta(historico)
    except OllamaError as erro:
        # Nada é salvo: o usuário pode simplesmente reenviar a mesma mensagem.
        return JsonResponse({'erro': str(erro)}, status=503)

    with transaction.atomic():
        Mensagem.objects.create(conversa=conversa, papel=Mensagem.Papel.USUARIO, conteudo=texto)
        Mensagem.objects.create(conversa=conversa, papel=Mensagem.Papel.ASSISTENTE, conteudo=resposta)
        if not anteriores:
            conversa.titulo = texto[:50] + ('…' if len(texto) > 50 else '')
        conversa.save()  # atualiza `atualizada_em` para a conversa subir na lista

    return JsonResponse({'resposta': resposta, 'titulo': conversa.titulo})

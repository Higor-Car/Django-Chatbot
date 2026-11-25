"""Cliente mínimo para a API do Ollama (https://ollama.com), usando só a biblioteca padrão."""

import json
import urllib.error
import urllib.request

from django.conf import settings


class OllamaError(Exception):
    """Erro com mensagem amigável para mostrar ao usuário."""


def gerar_resposta(mensagens):
    """Envia o histórico ao Ollama e devolve o texto da resposta.

    `mensagens` é uma lista de dicts no formato {'role': 'user'|'assistant', 'content': '...'}.
    """
    payload = {
        'model': settings.OLLAMA_MODEL,
        'messages': [{'role': 'system', 'content': settings.CHATBOT_SYSTEM_PROMPT}, *mensagens],
        'stream': False,
    }
    requisicao = urllib.request.Request(
        f"{settings.OLLAMA_URL.rstrip('/')}/api/chat",
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    try:
        with urllib.request.urlopen(requisicao, timeout=settings.OLLAMA_TIMEOUT) as resposta:
            dados = json.loads(resposta.read().decode('utf-8'))
    except urllib.error.HTTPError as erro:
        if erro.code == 404:
            raise OllamaError(
                f'O modelo "{settings.OLLAMA_MODEL}" não foi encontrado. '
                f'Rode no terminal: ollama pull {settings.OLLAMA_MODEL}'
            ) from erro
        raise OllamaError(f'O Ollama respondeu com erro {erro.code}.') from erro
    except urllib.error.URLError as erro:
        raise OllamaError(
            'Não consegui falar com o Ollama. Verifique se ele está instalado e aberto '
            f'(endereço configurado: {settings.OLLAMA_URL}).'
        ) from erro
    except TimeoutError as erro:
        raise OllamaError('O modelo demorou demais para responder. Tente de novo.') from erro

    conteudo = (dados.get('message') or {}).get('content', '').strip()
    if not conteudo:
        raise OllamaError('O modelo devolveu uma resposta vazia.')
    return conteudo

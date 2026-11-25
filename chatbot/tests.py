import json
import urllib.error
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Conversa, Mensagem
from .ollama import OllamaError, gerar_resposta


class RespostaFalsa:
    """Imita o objeto devolvido por urllib.request.urlopen."""

    def __init__(self, dados):
        self._corpo = json.dumps(dados).encode('utf-8')

    def read(self):
        return self._corpo

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@override_settings(OLLAMA_URL='http://ollama.teste', OLLAMA_MODEL='modelo-teste', CHATBOT_SYSTEM_PROMPT='Seja breve.')
class ClienteOllamaTests(TestCase):
    @mock.patch('chatbot.ollama.urllib.request.urlopen')
    def test_envia_prompt_de_sistema_e_historico(self, urlopen):
        urlopen.return_value = RespostaFalsa({'message': {'role': 'assistant', 'content': ' Olá! '}})

        resposta = gerar_resposta([{'role': 'user', 'content': 'Oi'}])

        self.assertEqual(resposta, 'Olá!')
        requisicao = urlopen.call_args.args[0]
        self.assertEqual(requisicao.full_url, 'http://ollama.teste/api/chat')
        enviado = json.loads(requisicao.data)
        self.assertEqual(enviado['model'], 'modelo-teste')
        self.assertFalse(enviado['stream'])
        self.assertEqual(enviado['messages'], [
            {'role': 'system', 'content': 'Seja breve.'},
            {'role': 'user', 'content': 'Oi'},
        ])

    @mock.patch('chatbot.ollama.urllib.request.urlopen', side_effect=urllib.error.URLError('recusado'))
    def test_ollama_desligado_vira_erro_amigavel(self, _):
        with self.assertRaisesMessage(OllamaError, 'Não consegui falar com o Ollama'):
            gerar_resposta([{'role': 'user', 'content': 'Oi'}])

    @mock.patch('chatbot.ollama.urllib.request.urlopen')
    def test_modelo_nao_baixado_sugere_pull(self, urlopen):
        urlopen.side_effect = urllib.error.HTTPError('url', 404, 'Not Found', {}, None)
        with self.assertRaisesMessage(OllamaError, 'ollama pull modelo-teste'):
            gerar_resposta([{'role': 'user', 'content': 'Oi'}])


class ChatViewsTests(TestCase):
    def setUp(self):
        self.conversa = Conversa.objects.create()
        self.url_enviar = reverse('chatbot:enviar_mensagem', args=[self.conversa.pk])

    def test_pagina_inicial_e_da_conversa_carregam(self):
        self.assertEqual(self.client.get(reverse('chatbot:inicio')).status_code, 200)
        resposta = self.client.get(reverse('chatbot:conversa', args=[self.conversa.pk]))
        self.assertContains(resposta, 'Nova conversa')

    def test_nova_conversa_redireciona_para_ela(self):
        resposta = self.client.post(reverse('chatbot:nova_conversa'))
        nova = Conversa.objects.exclude(pk=self.conversa.pk).get()
        self.assertRedirects(resposta, reverse('chatbot:conversa', args=[nova.pk]))

    @mock.patch('chatbot.views.gerar_resposta', return_value='Tudo ótimo!')
    def test_enviar_salva_mensagens_e_define_titulo(self, gerar):
        resposta = self.client.post(self.url_enviar, {'mensagem': '  Como você está?  '})

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {'resposta': 'Tudo ótimo!', 'titulo': 'Como você está?'})
        gerar.assert_called_once_with([{'role': 'user', 'content': 'Como você está?'}])
        self.assertEqual(
            list(self.conversa.mensagens.values_list('papel', 'conteudo')),
            [('user', 'Como você está?'), ('assistant', 'Tudo ótimo!')],
        )

    @mock.patch('chatbot.views.gerar_resposta', return_value='Resposta 2')
    def test_envia_historico_anterior_como_contexto(self, gerar):
        Mensagem.objects.create(conversa=self.conversa, papel='user', conteudo='Meu nome é Ana')
        Mensagem.objects.create(conversa=self.conversa, papel='assistant', conteudo='Oi, Ana!')
        self.conversa.titulo = 'Apresentação'
        self.conversa.save()

        self.client.post(self.url_enviar, {'mensagem': 'Qual é meu nome?'})

        gerar.assert_called_once_with([
            {'role': 'user', 'content': 'Meu nome é Ana'},
            {'role': 'assistant', 'content': 'Oi, Ana!'},
            {'role': 'user', 'content': 'Qual é meu nome?'},
        ])
        self.conversa.refresh_from_db()
        self.assertEqual(self.conversa.titulo, 'Apresentação')  # título só muda na 1ª mensagem

    @override_settings(CHATBOT_HISTORY_LIMIT=2)
    @mock.patch('chatbot.views.gerar_resposta', return_value='ok')
    def test_historico_respeita_limite(self, gerar):
        for i in range(5):
            Mensagem.objects.create(conversa=self.conversa, papel='user', conteudo=f'm{i}')

        self.client.post(self.url_enviar, {'mensagem': 'nova'})

        enviados = [m['content'] for m in gerar.call_args.args[0]]
        self.assertEqual(enviados, ['m3', 'm4', 'nova'])

    @mock.patch('chatbot.views.gerar_resposta', side_effect=OllamaError('Ollama fora do ar'))
    def test_erro_do_ollama_nao_salva_nada(self, _):
        resposta = self.client.post(self.url_enviar, {'mensagem': 'Oi'})

        self.assertEqual(resposta.status_code, 503)
        self.assertEqual(resposta.json(), {'erro': 'Ollama fora do ar'})
        self.assertFalse(Mensagem.objects.exists())

    @mock.patch('chatbot.views.gerar_resposta')
    def test_mensagem_vazia_ou_longa_e_rejeitada(self, gerar):
        self.assertEqual(self.client.post(self.url_enviar, {'mensagem': '   '}).status_code, 400)
        self.assertEqual(self.client.post(self.url_enviar, {'mensagem': 'x' * 4001}).status_code, 400)
        gerar.assert_not_called()

    def test_enviar_exige_post(self):
        self.assertEqual(self.client.get(self.url_enviar).status_code, 405)

    def test_excluir_conversa(self):
        resposta = self.client.post(reverse('chatbot:excluir_conversa', args=[self.conversa.pk]))
        self.assertRedirects(resposta, reverse('chatbot:inicio'))
        self.assertFalse(Conversa.objects.exists())

    def test_excluir_conversa_via_menu_responde_json(self):
        outra = Conversa.objects.create(titulo='Fica')
        resposta = self.client.post(
            reverse('chatbot:excluir_conversa', args=[self.conversa.pk]),
            headers={'Accept': 'application/json'},
        )
        self.assertEqual(resposta.json(), {'ok': True})
        self.assertEqual(list(Conversa.objects.all()), [outra])

    def test_renomear_conversa(self):
        url = reverse('chatbot:renomear_conversa', args=[self.conversa.pk])
        resposta = self.client.post(url, {'titulo': '  Receitas de bolo  '})
        self.assertEqual(resposta.json(), {'titulo': 'Receitas de bolo'})
        self.conversa.refresh_from_db()
        self.assertEqual(self.conversa.titulo, 'Receitas de bolo')

    def test_renomear_nao_muda_ordem_da_lista(self):
        mais_recente = Conversa.objects.create(titulo='Mais recente')
        self.client.post(reverse('chatbot:renomear_conversa', args=[self.conversa.pk]), {'titulo': 'Novo nome'})
        self.assertEqual(Conversa.objects.first(), mais_recente)

    def test_renomear_rejeita_nome_vazio(self):
        url = reverse('chatbot:renomear_conversa', args=[self.conversa.pk])
        self.assertEqual(self.client.post(url, {'titulo': '   '}).status_code, 400)
        self.conversa.refresh_from_db()
        self.assertEqual(self.conversa.titulo, 'Nova conversa')

    def test_pagina_mostra_menu_de_opcoes(self):
        resposta = self.client.get(reverse('chatbot:conversa', args=[self.conversa.pk]))
        self.assertContains(resposta, 'aria-haspopup="menu"')
        self.assertContains(resposta, reverse('chatbot:renomear_conversa', args=[self.conversa.pk]))

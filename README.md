# Django Chatbot

Chatbot em Django que usa o [Ollama](https://ollama.com) para rodar um modelo de IA no próprio computador, sem custo.

## Como rodar

1. Instale o Ollama: https://ollama.com/download
2. Baixe um modelo (uma vez só):
   ```
   ollama pull llama3.2
   ```
3. Instale as dependências e prepare o banco:
   ```
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   .venv\Scripts\python.exe manage.py migrate
   ```
4. Suba o servidor e abra http://localhost:8000
   ```
   .venv\Scripts\python.exe manage.py runserver
   ```

## Configuração

Em `config/settings.py` (ou por variável de ambiente):

| Variável         | Padrão                   | Para que serve                         |
|------------------|--------------------------|----------------------------------------|
| `OLLAMA_URL`     | `http://127.0.0.1:11434` | Endereço do Ollama                     |
| `OLLAMA_MODEL`   | `llama3.2`               | Modelo usado (ex.: `qwen2.5`, `gemma3`) |
| `OLLAMA_TIMEOUT` | `120`                    | Segundos de espera pela resposta       |

## Testes

```
.venv\Scripts\python.exe manage.py test chatbot
```

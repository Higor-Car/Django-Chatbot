from django.db import models


class Conversa(models.Model):
    titulo = models.CharField(max_length=100, default='Nova conversa')
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-atualizada_em']

    def __str__(self):
        return self.titulo


class Mensagem(models.Model):
    class Papel(models.TextChoices):
        USUARIO = 'user', 'Usuário'
        ASSISTENTE = 'assistant', 'Assistente'

    conversa = models.ForeignKey(Conversa, on_delete=models.CASCADE, related_name='mensagens')
    papel = models.CharField(max_length=10, choices=Papel.choices)
    conteudo = models.TextField()
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['criada_em', 'id']
        verbose_name_plural = 'mensagens'

    def __str__(self):
        return f'{self.get_papel_display()}: {self.conteudo[:50]}'

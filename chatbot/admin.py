from django.contrib import admin

from .models import Conversa, Mensagem


class MensagemInline(admin.TabularInline):
    model = Mensagem
    extra = 0
    readonly_fields = ['papel', 'conteudo', 'criada_em']


@admin.register(Conversa)
class ConversaAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'criada_em', 'atualizada_em']
    search_fields = ['titulo']
    inlines = [MensagemInline]


@admin.register(Mensagem)
class MensagemAdmin(admin.ModelAdmin):
    list_display = ['conversa', 'papel', 'conteudo', 'criada_em']
    list_filter = ['papel']
    search_fields = ['conteudo']

from django.contrib import admin

from .models import Cliente, CustoProduto, Encomenda


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nome', 'telefone')
    search_fields = ('nome', 'telefone')


@admin.register(Encomenda)
class EncomendaAdmin(admin.ModelAdmin):
    list_display = (
        'produto',
        'sabor',
        'cliente',
        'data_entrega',
        'status',
        'valor_cobrado',
    )
    list_filter = ('status', 'data_entrega')
    search_fields = ('produto', 'sabor', 'cliente__nome')


@admin.register(CustoProduto)
class CustoProdutoAdmin(admin.ModelAdmin):
    list_display = ('produto', 'sabor', 'custo_producao', 'data_atualizacao')
    search_fields = ('produto', 'sabor')

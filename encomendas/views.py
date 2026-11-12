from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import DecimalField, OuterRef, Subquery
from django.http import HttpResponse
from django.shortcuts import redirect, render

from .forms import EncomendaForm
from .models import CustoProduto, Encomenda

STATUS_FILTROS = [
    ('todas', 'Todas'),
    (Encomenda.Status.PENDENTE, 'Pendentes'),
    (Encomenda.Status.EM_PRODUCAO, 'Em produção'),
    (Encomenda.Status.ENTREGUE, 'Entregues'),
]

STATUS_META = {
    Encomenda.Status.PENDENTE: {
        'icone': '⏳',
        'classe': 'status-pendente',
        'rotulo': 'Pendente',
    },
    Encomenda.Status.EM_PRODUCAO: {
        'icone': '◐',
        'classe': 'status-em-producao',
        'rotulo': 'Em produção',
    },
    Encomenda.Status.ENTREGUE: {
        'icone': '✓',
        'classe': 'status-entregue',
        'rotulo': 'Entregue',
    },
}


def _menu_context(user):
    display_name = user.get_short_name() or user.get_username()
    initial = (display_name[:1] or '?').upper()
    return {
        'display_name': display_name,
        'user_initial': initial,
    }


def _montar_itens_encomenda(encomendas):
    itens = []
    for encomenda in encomendas:
        meta = STATUS_META.get(
            encomenda.status,
            {
                'icone': '•',
                'classe': 'status-desconhecido',
                'rotulo': encomenda.get_status_display(),
            },
        )
        custo = encomenda.custo_producao
        if custo is None:
            margem_texto = 'custo não cadastrado'
            margem_valor = None
        else:
            margem_valor = encomenda.valor_cobrado - custo
            margem_texto = f'R$ {margem_valor:.2f}'

        itens.append(
            {
                'encomenda': encomenda,
                'status_icone': meta['icone'],
                'status_classe': meta['classe'],
                'status_rotulo': meta['rotulo'],
                'margem_texto': margem_texto,
                'margem_valor': margem_valor,
            }
        )
    return itens


@login_required
def home(request):
    return render(request, 'home.html', _menu_context(request.user))


@login_required
def nova_encomenda(request):
    if request.method == 'POST':
        form = EncomendaForm(request.POST)
        if form.is_valid():
            encomenda = form.save()
            messages.success(
                request,
                f'Encomenda de {encomenda.cliente.nome} salva com sucesso.',
            )
            return redirect('minhas_encomendas')
    else:
        form = EncomendaForm()

    return render(request, 'nova_encomenda.html', {'form': form})


@login_required
def minhas_encomendas(request):
    status_filtro = request.GET.get('status', 'todas')
    status_validos = {valor for valor, _ in STATUS_FILTROS}
    if status_filtro not in status_validos:
        status_filtro = 'todas'

    custo_subquery = CustoProduto.objects.filter(
        produto=OuterRef('produto'),
        sabor=OuterRef('sabor'),
    ).values('custo_producao')[:1]

    queryset = (
        Encomenda.objects.select_related('cliente')
        .annotate(
            custo_producao=Subquery(
                custo_subquery,
                output_field=DecimalField(max_digits=10, decimal_places=2),
            )
        )
        .order_by('data_entrega', 'id')
    )

    if status_filtro != 'todas':
        queryset = queryset.filter(status=status_filtro)

    paginator = Paginator(queryset, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    itens = _montar_itens_encomenda(page_obj.object_list)

    return render(
        request,
        'minhas_encomendas.html',
        {
            'itens': itens,
            'page_obj': page_obj,
            'status_filtro': status_filtro,
            'status_filtros': STATUS_FILTROS,
        },
    )


@login_required
def custos_produtos(request):
    return HttpResponse('Custos de produtos — em breve')

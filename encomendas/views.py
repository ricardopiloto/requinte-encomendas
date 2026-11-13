from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import DecimalField, OuterRef, Subquery
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import CustoProdutoForm, EncomendaForm
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

STATUS_AVANCO = {
    Encomenda.Status.PENDENTE: Encomenda.Status.EM_PRODUCAO,
    Encomenda.Status.EM_PRODUCAO: Encomenda.Status.ENTREGUE,
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

        proximo_status = STATUS_AVANCO.get(encomenda.status)
        proximo_meta = STATUS_META.get(proximo_status) if proximo_status else None

        itens.append(
            {
                'encomenda': encomenda,
                'status_icone': meta['icone'],
                'status_classe': meta['classe'],
                'status_rotulo': meta['rotulo'],
                'margem_texto': margem_texto,
                'margem_valor': margem_valor,
                'proximo_status': proximo_status,
                'proximo_status_icone': (
                    proximo_meta['icone'] if proximo_meta else None
                ),
                'proximo_status_classe': (
                    proximo_meta['classe'] if proximo_meta else None
                ),
                'proximo_status_rotulo': (
                    proximo_meta['rotulo'] if proximo_meta else None
                ),
                'confirmacao_avanco': (
                    f'Marcar como {proximo_meta["rotulo"].lower()}?'
                    if proximo_meta
                    else None
                ),
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

    return render(
        request,
        'encomenda_form.html',
        {
            'form': form,
            'titulo': 'Nova encomenda',
            'botao_salvar': 'Salvar encomenda',
            'cancel_url': reverse('home'),
        },
    )


@login_required
def editar_encomenda(request, pk):
    encomenda = get_object_or_404(Encomenda.objects.select_related('cliente'), pk=pk)

    if request.method == 'POST':
        form = EncomendaForm(request.POST, instance=encomenda)
        if form.is_valid():
            atualizada = form.save()
            messages.success(
                request,
                f'Dados da encomenda de {atualizada.cliente.nome} atualizados.',
            )
            return redirect('minhas_encomendas')
    else:
        form = EncomendaForm(instance=encomenda)

    return render(
        request,
        'encomenda_form.html',
        {
            'form': form,
            'titulo': 'Editar encomenda',
            'botao_salvar': 'Salvar alterações',
            'cancel_url': reverse('minhas_encomendas'),
        },
    )


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
def excluir_encomenda(request, pk):
    encomenda = get_object_or_404(
        Encomenda.objects.select_related('cliente'),
        pk=pk,
    )

    if request.method == 'POST':
        nome_cliente = encomenda.cliente.nome
        encomenda.delete()
        messages.success(
            request,
            f'Encomenda de {nome_cliente} foi excluída.',
        )
        return redirect('minhas_encomendas')

    return render(
        request,
        'excluir_encomenda.html',
        {'encomenda': encomenda},
    )


@login_required
@require_POST
def avancar_status_encomenda(request, pk):
    encomenda = get_object_or_404(Encomenda, pk=pk)
    proximo_status = STATUS_AVANCO.get(encomenda.status)

    if proximo_status is None:
        messages.error(
            request,
            'Esta encomenda já está entregue e não pode avançar de status pela listagem.',
        )
    else:
        encomenda.status = proximo_status
        encomenda.save(update_fields=['status'])
        rotulo = STATUS_META[proximo_status]['rotulo']
        messages.success(
            request,
            f'Encomenda de {encomenda.cliente.nome} marcada como {rotulo.lower()}.',
        )

    status_filtro = request.POST.get('status', 'todas')
    if status_filtro and status_filtro != 'todas':
        return redirect(f"{reverse('minhas_encomendas')}?status={status_filtro}")
    return redirect('minhas_encomendas')


@login_required
def custos_produtos(request):
    if request.method == 'POST':
        form = CustoProdutoForm(request.POST)
        if form.is_valid():
            custo = form.save()
            if form.created:
                messages.success(
                    request,
                    f'Custo de {custo.produto} ({custo.sabor}) cadastrado.',
                )
            else:
                messages.success(
                    request,
                    f'Custo de {custo.produto} ({custo.sabor}) atualizado.',
                )
            return redirect('custos_produtos')
    else:
        initial = {}
        edit_id = request.GET.get('edit')
        if edit_id:
            existente = get_object_or_404(CustoProduto, pk=edit_id)
            initial = {
                'produto': existente.produto,
                'sabor': existente.sabor,
                'custo_producao': existente.custo_producao,
            }
        form = CustoProdutoForm(initial=initial)

    custos = CustoProduto.objects.order_by('produto', 'sabor')
    return render(
        request,
        'custos_produtos.html',
        {
            'form': form,
            'custos': custos,
            'editando': bool(request.GET.get('edit') or request.POST.get('edit')),
            'edit_id': request.GET.get('edit') or request.POST.get('edit', ''),
        },
    )

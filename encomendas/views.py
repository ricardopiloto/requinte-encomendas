from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render

from .forms import EncomendaForm
from .models import Encomenda


def _menu_context(user):
    display_name = user.get_short_name() or user.get_username()
    initial = (display_name[:1] or '?').upper()
    return {
        'display_name': display_name,
        'user_initial': initial,
    }


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
    encomendas = (
        Encomenda.objects.select_related('cliente')
        .order_by('data_entrega', 'id')
    )
    return render(
        request,
        'minhas_encomendas.html',
        {'encomendas': encomendas},
    )


@login_required
def custos_produtos(request):
    return HttpResponse('Custos de produtos — em breve')

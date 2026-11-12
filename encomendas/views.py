from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render


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
    return HttpResponse('Nova encomenda — em breve')


@login_required
def minhas_encomendas(request):
    return HttpResponse('Minhas encomendas — em breve')


@login_required
def custos_produtos(request):
    return HttpResponse('Custos de produtos — em breve')

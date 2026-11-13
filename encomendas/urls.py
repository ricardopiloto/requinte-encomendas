from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('encomendas/nova/', views.nova_encomenda, name='nova_encomenda'),
    path(
        'encomendas/<int:pk>/editar/',
        views.editar_encomenda,
        name='editar_encomenda',
    ),
    path(
        'encomendas/<int:pk>/excluir/',
        views.excluir_encomenda,
        name='excluir_encomenda',
    ),
    path(
        'encomendas/<int:pk>/avancar-status/',
        views.avancar_status_encomenda,
        name='avancar_status_encomenda',
    ),
    path('encomendas/', views.minhas_encomendas, name='minhas_encomendas'),
    path('resumo/', views.resumo_financeiro, name='resumo_financeiro'),
    path('custos/', views.custos_produtos, name='custos_produtos'),
    path(
        'custos/<int:pk>/excluir/',
        views.excluir_custo_produto,
        name='excluir_custo_produto',
    ),
    path(
        'login/',
        auth_views.LoginView.as_view(template_name='login.html'),
        name='login',
    ),
    path(
        'logout/',
        auth_views.LogoutView.as_view(),
        name='logout',
    ),
]

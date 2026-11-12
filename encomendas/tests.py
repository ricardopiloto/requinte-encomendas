from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import DecimalField, OuterRef, Subquery
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .forms import EncomendaForm
from .models import Cliente, CustoProduto, Encomenda
from .views import _montar_itens_encomenda

User = get_user_model()


def _queryset_com_custo():
    custo_subquery = CustoProduto.objects.filter(
        produto=OuterRef('produto'),
        sabor=OuterRef('sabor'),
    ).values('custo_producao')[:1]
    return Encomenda.objects.select_related('cliente').annotate(
        custo_producao=Subquery(
            custo_subquery,
            output_field=DecimalField(max_digits=10, decimal_places=2),
        )
    )


class MargemCalculoTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nome='Maria', telefone='11999999999')
        CustoProduto.objects.create(
            produto='Bolo',
            sabor='Chocolate',
            custo_producao=Decimal('85.00'),
        )
        CustoProduto.objects.create(
            produto='Bolo',
            sabor='Morango',
            custo_producao=Decimal('90.00'),
        )
        CustoProduto.objects.create(
            produto='Docinho',
            sabor='Brigadeiro',
            custo_producao=Decimal('60.00'),
        )

    def test_margem_por_combinacao_produto_sabor(self):
        casos = [
            ('Bolo', 'Chocolate', Decimal('180.00'), Decimal('95.00')),
            ('Bolo', 'Morango', Decimal('200.00'), Decimal('110.00')),
            ('Docinho', 'Brigadeiro', Decimal('120.00'), Decimal('60.00')),
        ]

        for produto, sabor, valor_cobrado, margem_esperada in casos:
            with self.subTest(produto=produto, sabor=sabor):
                Encomenda.objects.create(
                    cliente=self.cliente,
                    produto=produto,
                    sabor=sabor,
                    data_entrega=date(2026, 11, 14),
                    valor_cobrado=valor_cobrado,
                )

        itens = {
            (item['encomenda'].produto, item['encomenda'].sabor): item
            for item in _montar_itens_encomenda(_queryset_com_custo())
        }

        for produto, sabor, _, margem_esperada in casos:
            item = itens[(produto, sabor)]
            self.assertEqual(item['margem_valor'], margem_esperada)
            self.assertEqual(item['margem_texto'], f'R$ {margem_esperada:.2f}')

    def test_margem_quando_custo_nao_cadastrado(self):
        Encomenda.objects.create(
            cliente=self.cliente,
            produto='Torta',
            sabor='Limão',
            data_entrega=date(2026, 11, 20),
            valor_cobrado=Decimal('150.00'),
        )

        item = _montar_itens_encomenda(_queryset_com_custo())[0]

        self.assertIsNone(item['margem_valor'])
        self.assertEqual(item['margem_texto'], 'custo não cadastrado')

    def test_margem_nao_usa_custo_de_outra_combinacao(self):
        Encomenda.objects.create(
            cliente=self.cliente,
            produto='Bolo',
            sabor='Baunilha',
            data_entrega=date(2026, 11, 18),
            valor_cobrado=Decimal('180.00'),
        )

        item = _montar_itens_encomenda(_queryset_com_custo())[0]

        self.assertIsNone(item['margem_valor'])
        self.assertEqual(item['margem_texto'], 'custo não cadastrado')


class EncomendaFormValidationTests(TestCase):
    def _dados_validos(self):
        return {
            'cliente': 'Maria',
            'produto': 'Bolo',
            'sabor': 'Chocolate',
            'data_entrega': '2026-11-14',
            'valor_cobrado': '180.00',
        }

    def test_formulario_valido_com_todos_os_campos(self):
        form = EncomendaForm(data=self._dados_validos())
        self.assertTrue(form.is_valid(), form.errors)

    def test_rejeita_quando_campo_obrigatorio_esta_vazio(self):
        campos = [
            'cliente',
            'produto',
            'sabor',
            'data_entrega',
            'valor_cobrado',
        ]

        for campo in campos:
            with self.subTest(campo=campo):
                dados = self._dados_validos()
                dados[campo] = ''
                form = EncomendaForm(data=dados)

                self.assertFalse(form.is_valid())
                self.assertIn(campo, form.errors)


class EncomendaStatusModelTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nome='Maria', telefone='11999999999')

    def _nova_encomenda(self, status=None):
        kwargs = {
            'cliente': self.cliente,
            'produto': 'Bolo',
            'sabor': 'Chocolate',
            'data_entrega': date(2026, 11, 14),
            'valor_cobrado': Decimal('180.00'),
        }
        if status is not None:
            kwargs['status'] = status
        return Encomenda(**kwargs)

    def test_status_padrao_e_pendente(self):
        encomenda = self._nova_encomenda()
        encomenda.full_clean()
        encomenda.save()

        self.assertEqual(encomenda.status, Encomenda.Status.PENDENTE)

    def test_aceita_valores_validos_de_status(self):
        for status in Encomenda.Status.values:
            with self.subTest(status=status):
                encomenda = self._nova_encomenda(status=status)
                encomenda.full_clean()
                encomenda.save()

                encomenda.refresh_from_db()
                self.assertEqual(encomenda.status, status)
                self.assertIn(encomenda.status, dict(Encomenda.Status.choices))

    def test_rejeita_status_invalido(self):
        encomenda = self._nova_encomenda(status='cancelada')

        with self.assertRaises(ValidationError) as contexto:
            encomenda.full_clean()

        self.assertIn('status', contexto.exception.message_dict)


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'])
class FluxoEncomendaIntegracaoTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.password = 'senha-segura-123'
        self.user = User.objects.create_user(
            username='deise',
            password=self.password,
            first_name='Deise',
        )
        CustoProduto.objects.create(
            produto='Bolo',
            sabor='Chocolate',
            custo_producao=Decimal('85.00'),
        )

    def test_login_cadastro_e_listagem_com_status_e_margem(self):
        login_response = self.client.post(
            reverse('login'),
            {
                'username': self.user.username,
                'password': self.password,
            },
        )
        self.assertEqual(login_response.status_code, 302)
        self.assertEqual(login_response.url, reverse('home'))

        cadastro_response = self.client.post(
            reverse('nova_encomenda'),
            {
                'cliente': 'Maria',
                'produto': 'Bolo',
                'sabor': 'Chocolate',
                'data_entrega': '2026-11-14',
                'valor_cobrado': '180.00',
            },
        )
        self.assertEqual(cadastro_response.status_code, 302)
        self.assertEqual(cadastro_response.url, reverse('minhas_encomendas'))

        encomenda = Encomenda.objects.get()
        self.assertEqual(encomenda.cliente.nome, 'Maria')
        self.assertEqual(encomenda.produto, 'Bolo')
        self.assertEqual(encomenda.sabor, 'Chocolate')
        self.assertEqual(encomenda.status, Encomenda.Status.PENDENTE)
        self.assertEqual(encomenda.valor_cobrado, Decimal('180.00'))

        listagem_response = self.client.get(reverse('minhas_encomendas'))
        self.assertEqual(listagem_response.status_code, 200)
        conteudo = listagem_response.content.decode()

        self.assertIn('Maria — Bolo', conteudo)
        self.assertIn('status-pendente', conteudo)
        self.assertIn('Pendente', conteudo)
        self.assertIn('⏳', conteudo)
        self.assertIn('Entrega: 14/11/2026', conteudo)
        self.assertIn('Cobrado R$ 180.00', conteudo)
        self.assertIn('Margem R$ 95.00', conteudo)
        self.assertContains(
            listagem_response,
            'Encomenda de Maria salva com sucesso.',
        )

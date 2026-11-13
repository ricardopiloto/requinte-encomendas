import json
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import DecimalField, OuterRef, Subquery
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import number_format

from .forms import ITEM_OUTRO, EncomendaForm
from .models import Cliente, CustoProduto, Encomenda
from .views import _montar_itens_encomenda

User = get_user_model()


def _moeda(valor):
    return f'R$ {number_format(valor, decimal_pos=2, use_l10n=True)}'


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
            self.assertEqual(item['margem_texto'], _moeda(margem_esperada))

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
            'item': ITEM_OUTRO,
            'produto_outro': 'Bolo',
            'sabor_outro': 'Chocolate',
            'data_entrega': '14/11/2026',
            'valor_cobrado': '180.00',
        }

    def test_formulario_valido_com_todos_os_campos(self):
        form = EncomendaForm(data=self._dados_validos())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['produto'], 'Bolo')
        self.assertEqual(form.cleaned_data['sabor'], 'Chocolate')

    def test_formulario_valido_com_item_cadastrado(self):
        custo = CustoProduto.objects.create(
            produto='Bolo',
            sabor='Chocolate',
            custo_producao=Decimal('85.00'),
        )
        form = EncomendaForm(
            data={
                'cliente': 'Maria',
                'item': str(custo.pk),
                'data_entrega': '14/11/2026',
                'valor_cobrado': '180.00',
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['produto'], 'Bolo')
        self.assertEqual(form.cleaned_data['sabor'], 'Chocolate')

    def test_rejeita_quando_campo_obrigatorio_esta_vazio(self):
        campos = [
            'cliente',
            'item',
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

    def test_rejeita_outro_sem_produto_ou_sabor(self):
        for campo in ('produto_outro', 'sabor_outro'):
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
        self.custo_bolo = CustoProduto.objects.create(
            produto='Bolo',
            sabor='Chocolate',
            custo_producao=Decimal('85.00'),
        )

    def _item_bolo_chocolate(self):
        return str(
            CustoProduto.objects.get(produto='Bolo', sabor='Chocolate').pk
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
                'item': self._item_bolo_chocolate(),
                'data_entrega': '14/11/2026',
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
        self.assertEqual(encomenda.data_entrega, date(2026, 11, 14))

        listagem_response = self.client.get(reverse('minhas_encomendas'))
        self.assertEqual(listagem_response.status_code, 200)
        conteudo = listagem_response.content.decode()

        self.assertIn('Maria — Bolo', conteudo)
        self.assertIn('status-pendente', conteudo)
        self.assertIn('Pendente', conteudo)
        self.assertIn('⏳', conteudo)
        self.assertIn('Entrega: 14/11/2026', conteudo)
        self.assertIn(_moeda(Decimal('180.00')), conteudo)
        self.assertIn(f'Margem {_moeda(Decimal("95.00"))}', conteudo)
        self.assertContains(
            listagem_response,
            'Encomenda de Maria salva com sucesso.',
        )

    def test_custo_via_tela_reflete_margem_na_listagem(self):
        custo_producao = Decimal('70.00')
        valor_cobrado = Decimal('180.00')
        margem_esperada = valor_cobrado - custo_producao

        login_response = self.client.post(
            reverse('login'),
            {
                'username': self.user.username,
                'password': self.password,
            },
        )
        self.assertEqual(login_response.status_code, 302)

        custo_response = self.client.post(
            reverse('custos_produtos'),
            {
                'produto': 'Bolo',
                'sabor': 'Chocolate',
                'custo_producao': str(custo_producao),
            },
        )
        self.assertEqual(custo_response.status_code, 302)
        self.assertEqual(custo_response.url, reverse('custos_produtos'))

        custo = CustoProduto.objects.get(produto='Bolo', sabor='Chocolate')
        self.assertEqual(custo.custo_producao, custo_producao)

        cadastro_response = self.client.post(
            reverse('nova_encomenda'),
            {
                'cliente': 'Maria',
                'item': self._item_bolo_chocolate(),
                'data_entrega': '14/11/2026',
                'valor_cobrado': str(valor_cobrado),
            },
        )
        self.assertEqual(cadastro_response.status_code, 302)
        self.assertEqual(cadastro_response.url, reverse('minhas_encomendas'))

        listagem_response = self.client.get(reverse('minhas_encomendas'))
        self.assertEqual(listagem_response.status_code, 200)
        self.assertContains(
            listagem_response,
            f'Margem {_moeda(margem_esperada)}',
        )

    def test_avanco_de_status_na_listagem_sem_retrocesso(self):
        login_response = self.client.post(
            reverse('login'),
            {
                'username': self.user.username,
                'password': self.password,
            },
        )
        self.assertEqual(login_response.status_code, 302)

        cadastro_response = self.client.post(
            reverse('nova_encomenda'),
            {
                'cliente': 'Carla',
                'item': self._item_bolo_chocolate(),
                'data_entrega': '15/11/2026',
                'valor_cobrado': '150.00',
            },
        )
        self.assertEqual(cadastro_response.status_code, 302)

        encomenda = Encomenda.objects.get()
        self.assertEqual(encomenda.status, Encomenda.Status.PENDENTE)

        listagem_pendente = self.client.get(reverse('minhas_encomendas'))
        self.assertContains(listagem_pendente, 'status-pendente')
        self.assertContains(listagem_pendente, 'Pendente')
        self.assertContains(listagem_pendente, 'Marcar como em produção?')
        self.assertContains(listagem_pendente, 'Em produção')
        self.assertNotContains(listagem_pendente, 'Marcar como entregue?')

        avanco_producao = self.client.post(
            reverse('avancar_status_encomenda', args=[encomenda.pk]),
            {'status': 'todas'},
        )
        self.assertEqual(avanco_producao.status_code, 302)
        encomenda.refresh_from_db()
        self.assertEqual(encomenda.status, Encomenda.Status.EM_PRODUCAO)

        listagem_producao = self.client.get(reverse('minhas_encomendas'))
        self.assertContains(listagem_producao, 'status-em-producao')
        self.assertContains(listagem_producao, 'Em produção')
        self.assertContains(listagem_producao, 'Marcar como entregue?')
        self.assertContains(
            listagem_producao,
            'Encomenda de Carla marcada como em produção.',
        )
        self.assertNotContains(listagem_producao, 'Marcar como pendente?')
        self.assertNotContains(listagem_producao, 'Marcar como em produção?')

        avanco_entregue = self.client.post(
            reverse('avancar_status_encomenda', args=[encomenda.pk]),
            {'status': 'todas'},
        )
        self.assertEqual(avanco_entregue.status_code, 302)
        encomenda.refresh_from_db()
        self.assertEqual(encomenda.status, Encomenda.Status.ENTREGUE)

        listagem_entregue = self.client.get(reverse('minhas_encomendas'))
        self.assertContains(listagem_entregue, 'status-entregue')
        self.assertContains(listagem_entregue, 'Entregue')
        self.assertContains(
            listagem_entregue,
            'Encomenda de Carla marcada como entregue.',
        )
        self.assertNotContains(listagem_entregue, 'Marcar como em produção?')
        self.assertNotContains(listagem_entregue, 'Marcar como entregue?')
        self.assertNotContains(listagem_entregue, 'Marcar como pendente?')

        tentativa_retrocesso = self.client.post(
            reverse('avancar_status_encomenda', args=[encomenda.pk]),
            {'status': 'todas'},
        )
        self.assertEqual(tentativa_retrocesso.status_code, 302)
        encomenda.refresh_from_db()
        self.assertEqual(encomenda.status, Encomenda.Status.ENTREGUE)

    def test_edicao_de_encomenda_atualiza_valor_e_margem_na_listagem(self):
        custo_producao = Decimal('85.00')
        valor_inicial = Decimal('180.00')
        valor_atualizado = Decimal('220.00')
        margem_atualizada = valor_atualizado - custo_producao

        login_response = self.client.post(
            reverse('login'),
            {
                'username': self.user.username,
                'password': self.password,
            },
        )
        self.assertEqual(login_response.status_code, 302)

        cadastro_response = self.client.post(
            reverse('nova_encomenda'),
            {
                'cliente': 'Juliana',
                'item': self._item_bolo_chocolate(),
                'data_entrega': '16/11/2026',
                'valor_cobrado': str(valor_inicial),
            },
        )
        self.assertEqual(cadastro_response.status_code, 302)

        encomenda = Encomenda.objects.get()
        self.assertEqual(encomenda.valor_cobrado, valor_inicial)

        edicao_response = self.client.post(
            reverse('editar_encomenda', args=[encomenda.pk]),
            {
                'cliente': 'Juliana',
                'item': self._item_bolo_chocolate(),
                'data_entrega': '16/11/2026',
                'valor_cobrado': str(valor_atualizado),
            },
        )
        self.assertEqual(edicao_response.status_code, 302)
        self.assertEqual(edicao_response.url, reverse('minhas_encomendas'))

        encomenda.refresh_from_db()
        self.assertEqual(encomenda.valor_cobrado, valor_atualizado)

        listagem_response = self.client.get(reverse('minhas_encomendas'))
        self.assertEqual(listagem_response.status_code, 200)
        self.assertContains(listagem_response, f'Cobrado {_moeda(valor_atualizado)}')
        self.assertContains(
            listagem_response,
            f'Margem {_moeda(margem_atualizada)}',
        )
        self.assertContains(
            listagem_response,
            'Dados da encomenda de Juliana atualizados.',
        )
        self.assertNotContains(listagem_response, f'Cobrado {_moeda(valor_inicial)}')
        self.assertNotContains(
            listagem_response,
            f'Margem {_moeda(Decimal("95.00"))}',
        )

    def test_exclusao_de_encomenda_exige_post_e_some_da_listagem(self):
        login_response = self.client.post(
            reverse('login'),
            {
                'username': self.user.username,
                'password': self.password,
            },
        )
        self.assertEqual(login_response.status_code, 302)

        cadastro_response = self.client.post(
            reverse('nova_encomenda'),
            {
                'cliente': 'Beatriz',
                'item': self._item_bolo_chocolate(),
                'data_entrega': '18/11/2026',
                'valor_cobrado': '160.00',
            },
        )
        self.assertEqual(cadastro_response.status_code, 302)

        encomenda = Encomenda.objects.get()
        pk = encomenda.pk

        confirmacao_get = self.client.get(
            reverse('excluir_encomenda', args=[pk]),
        )
        self.assertEqual(confirmacao_get.status_code, 200)
        self.assertContains(confirmacao_get, 'Beatriz')
        self.assertContains(confirmacao_get, 'Bolo')
        self.assertContains(confirmacao_get, '18/11/2026')
        self.assertTrue(Encomenda.objects.filter(pk=pk).exists())

        listagem_apos_get = self.client.get(reverse('minhas_encomendas'))
        self.assertContains(listagem_apos_get, 'Beatriz — Bolo')

        exclusao_post = self.client.post(
            reverse('excluir_encomenda', args=[pk]),
        )
        self.assertEqual(exclusao_post.status_code, 302)
        self.assertEqual(exclusao_post.url, reverse('minhas_encomendas'))
        self.assertFalse(Encomenda.objects.filter(pk=pk).exists())

        listagem_apos_post = self.client.get(reverse('minhas_encomendas'))
        self.assertNotContains(listagem_apos_post, 'Beatriz — Bolo')
        self.assertContains(
            listagem_apos_post,
            'Encomenda de Beatriz foi excluída.',
        )

    def test_formulario_exibe_opcoes_de_custo_produto(self):
        CustoProduto.objects.create(
            produto='Docinho',
            sabor='Brigadeiro',
            custo_producao=Decimal('40.00'),
        )

        login_response = self.client.post(
            reverse('login'),
            {
                'username': self.user.username,
                'password': self.password,
            },
        )
        self.assertEqual(login_response.status_code, 302)

        formulario = self.client.get(reverse('nova_encomenda'))
        self.assertEqual(formulario.status_code, 200)
        self.assertContains(formulario, 'Bolo (Chocolate)')
        self.assertContains(formulario, 'Docinho (Brigadeiro)')
        self.assertContains(formulario, 'Outro (informar manualmente)')
        self.assertContains(
            formulario,
            f'value="{self._item_bolo_chocolate()}"',
        )
        self.assertContains(formulario, f'value="{ITEM_OUTRO}"')

    def test_opcao_outro_cadastra_encomenda_sem_custo_existente(self):
        login_response = self.client.post(
            reverse('login'),
            {
                'username': self.user.username,
                'password': self.password,
            },
        )
        self.assertEqual(login_response.status_code, 302)

        self.assertFalse(
            CustoProduto.objects.filter(
                produto='Torta',
                sabor='Limão',
            ).exists()
        )

        cadastro_response = self.client.post(
            reverse('nova_encomenda'),
            {
                'cliente': 'Helena',
                'item': ITEM_OUTRO,
                'produto_outro': 'Torta',
                'sabor_outro': 'Limão',
                'data_entrega': '20/11/2026',
                'valor_cobrado': '95.00',
            },
        )
        self.assertEqual(cadastro_response.status_code, 302)
        self.assertEqual(cadastro_response.url, reverse('minhas_encomendas'))

        encomenda = Encomenda.objects.get()
        self.assertEqual(encomenda.cliente.nome, 'Helena')
        self.assertEqual(encomenda.produto, 'Torta')
        self.assertEqual(encomenda.sabor, 'Limão')
        self.assertFalse(
            CustoProduto.objects.filter(
                produto='Torta',
                sabor='Limão',
            ).exists()
        )

        listagem = self.client.get(reverse('minhas_encomendas'))
        self.assertContains(listagem, 'Helena — Torta')
        self.assertContains(listagem, 'custo não cadastrado')

    def test_cadastro_exibe_custo_de_producao_do_item_selecionavel(self):
        login_response = self.client.post(
            reverse('login'),
            {
                'username': self.user.username,
                'password': self.password,
            },
        )
        self.assertEqual(login_response.status_code, 302)

        formulario = self.client.get(reverse('nova_encomenda'))
        self.assertEqual(formulario.status_code, 200)
        self.assertContains(formulario, 'id="preview-custo"')
        self.assertContains(formulario, 'id="preview-margem"')
        self.assertContains(formulario, 'id="custos-data"')

        custos = json.loads(formulario.context['form'].custos_json)
        item_id = self._item_bolo_chocolate()
        self.assertIn(item_id, custos['por_item'])
        self.assertEqual(
            Decimal(custos['por_item'][item_id]),
            Decimal('85.00'),
        )
        self.assertEqual(
            Decimal(custos['por_par']['bolo|chocolate']),
            Decimal('85.00'),
        )

    def test_cadastro_indica_custo_nao_cadastrado_quando_sem_custo(self):
        login_response = self.client.post(
            reverse('login'),
            {
                'username': self.user.username,
                'password': self.password,
            },
        )
        self.assertEqual(login_response.status_code, 302)

        formulario = self.client.get(reverse('nova_encomenda'))
        self.assertEqual(formulario.status_code, 200)
        self.assertContains(formulario, 'custo não cadastrado')

        custos = json.loads(formulario.context['form'].custos_json)
        self.assertNotIn('torta|limão', custos['por_par'])
        self.assertEqual(custos['outro'], ITEM_OUTRO)
        self.assertNotIn(ITEM_OUTRO, custos['por_item'])

    def test_resumo_financeiro_soma_margens_entregues_por_periodo(self):
        login_response = self.client.post(
            reverse('login'),
            {
                'username': self.user.username,
                'password': self.password,
            },
        )
        self.assertEqual(login_response.status_code, 302)

        hoje = timezone.localdate()
        semana_inicio = hoje - timedelta(days=hoje.weekday())
        semana_fim = semana_inicio + timedelta(days=6)
        mes_inicio = hoje.replace(day=1)
        mes_fim = hoje.replace(day=monthrange(hoje.year, hoje.month)[1])

        data_na_semana = hoje
        data_mes_fora_semana = next(
            mes_inicio + timedelta(days=offset)
            for offset in range((mes_fim - mes_inicio).days + 1)
            if not (
                semana_inicio
                <= mes_inicio + timedelta(days=offset)
                <= semana_fim
            )
        )
        data_fora_mes = mes_inicio - timedelta(days=1)

        def data_br(valor):
            return valor.strftime('%d/%m/%Y')

        def cadastrar(cliente, data_entrega, valor_cobrado):
            response = self.client.post(
                reverse('nova_encomenda'),
                {
                    'cliente': cliente,
                    'item': self._item_bolo_chocolate(),
                    'data_entrega': data_br(data_entrega),
                    'valor_cobrado': valor_cobrado,
                },
            )
            self.assertEqual(response.status_code, 302)
            return Encomenda.objects.get(cliente__nome=cliente)

        def marcar_entregue(encomenda):
            for _ in range(2):
                response = self.client.post(
                    reverse('avancar_status_encomenda', args=[encomenda.pk]),
                    {'status': 'todas'},
                )
                self.assertEqual(response.status_code, 302)
            encomenda.refresh_from_db()
            self.assertEqual(encomenda.status, Encomenda.Status.ENTREGUE)

        # custo Bolo Chocolate = 85.00
        # margens: 100 (semana), 200 (mês fora da semana), 300 (fora do mês),
        # 400 (pendente na semana — não deve entrar)
        encomenda_semana = cadastrar('Rita', data_na_semana, '185.00')
        marcar_entregue(encomenda_semana)

        encomenda_mes = cadastrar('Sofia', data_mes_fora_semana, '285.00')
        marcar_entregue(encomenda_mes)

        encomenda_fora = cadastrar('Tania', data_fora_mes, '385.00')
        marcar_entregue(encomenda_fora)

        encomenda_pendente = cadastrar('Ursula', data_na_semana, '485.00')
        self.assertEqual(
            encomenda_pendente.status,
            Encomenda.Status.PENDENTE,
        )

        margem_semana_esperada = Decimal('100.00')
        margem_mes_esperada = Decimal('300.00')

        resumo = self.client.get(reverse('resumo_financeiro'))
        self.assertEqual(resumo.status_code, 200)
        self.assertEqual(resumo.context['semana_inicio'], semana_inicio)
        self.assertEqual(resumo.context['semana_fim'], semana_fim)
        self.assertEqual(resumo.context['mes_inicio'], mes_inicio)
        self.assertEqual(resumo.context['mes_fim'], mes_fim)
        self.assertEqual(
            resumo.context['margem_semana'],
            margem_semana_esperada,
        )
        self.assertEqual(resumo.context['margem_mes'], margem_mes_esperada)
        self.assertContains(resumo, 'Semana atual')
        self.assertContains(resumo, 'Mês atual')
        self.assertContains(resumo, _moeda(margem_semana_esperada))
        self.assertContains(resumo, _moeda(margem_mes_esperada))

    def test_listagem_ordena_pela_data_de_entrega_mais_proxima(self):
        login_response = self.client.post(
            reverse('login'),
            {
                'username': self.user.username,
                'password': self.password,
            },
        )
        self.assertEqual(login_response.status_code, 302)

        # Cadastro propositalmente fora de ordem cronológica.
        cadastros = [
            ('Vera', '25/11/2026', '180.00'),
            ('Ana', '12/11/2026', '170.00'),
            ('Paula', '20/11/2026', '190.00'),
        ]
        for cliente, data_entrega, valor_cobrado in cadastros:
            response = self.client.post(
                reverse('nova_encomenda'),
                {
                    'cliente': cliente,
                    'item': self._item_bolo_chocolate(),
                    'data_entrega': data_entrega,
                    'valor_cobrado': valor_cobrado,
                },
            )
            self.assertEqual(response.status_code, 302)

        self.assertEqual(Encomenda.objects.count(), 3)

        listagem = self.client.get(reverse('minhas_encomendas'))
        self.assertEqual(listagem.status_code, 200)

        nomes_ordenados = [
            item['encomenda'].cliente.nome
            for item in listagem.context['itens']
        ]
        datas_ordenadas = [
            item['encomenda'].data_entrega
            for item in listagem.context['itens']
        ]

        self.assertEqual(nomes_ordenados, ['Ana', 'Paula', 'Vera'])
        self.assertEqual(
            datas_ordenadas,
            [
                date(2026, 11, 12),
                date(2026, 11, 20),
                date(2026, 11, 25),
            ],
        )
        self.assertContains(listagem, 'Ana — Bolo')
        self.assertContains(listagem, 'Paula — Bolo')
        self.assertContains(listagem, 'Vera — Bolo')

        # Na HTML, a mais próxima deve aparecer antes das demais.
        conteudo = listagem.content.decode()
        pos_ana = conteudo.index('Ana — Bolo')
        pos_paula = conteudo.index('Paula — Bolo')
        pos_vera = conteudo.index('Vera — Bolo')
        self.assertLess(pos_ana, pos_paula)
        self.assertLess(pos_paula, pos_vera)

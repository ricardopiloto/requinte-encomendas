from decimal import Decimal

from django import forms

from .models import Cliente, CustoProduto, Encomenda

ITEM_OUTRO = '__outro__'


class EncomendaForm(forms.ModelForm):
    cliente = forms.CharField(
        label='Cliente',
        max_length=200,
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Nome do cliente',
                'autocomplete': 'name',
            }
        ),
        error_messages={
            'required': 'Informe o nome do cliente.',
        },
    )
    item = forms.ChoiceField(
        label='Produto e sabor',
        error_messages={
            'required': 'Selecione o produto e o sabor.',
            'invalid_choice': 'Selecione uma opção válida de produto e sabor.',
        },
    )
    produto_outro = forms.CharField(
        label='Produto (outro)',
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Bolo'}),
    )
    sabor_outro = forms.CharField(
        label='Sabor (outro)',
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Chocolate'}),
    )

    class Meta:
        model = Encomenda
        fields = ['data_entrega', 'valor_cobrado']
        labels = {
            'data_entrega': 'Data de entrega',
            'valor_cobrado': 'Valor cobrado',
        }
        widgets = {
            'data_entrega': forms.DateInput(
                format='%d/%m/%Y',
                attrs={
                    'type': 'text',
                    'placeholder': 'dd/mm/aaaa',
                    'inputmode': 'numeric',
                    'autocomplete': 'off',
                },
            ),
            'valor_cobrado': forms.NumberInput(
                attrs={
                    'placeholder': '0,00',
                    'step': '0.01',
                    'min': '0',
                    'inputmode': 'decimal',
                }
            ),
        }
        error_messages = {
            'data_entrega': {
                'required': 'Informe a data de entrega.',
                'invalid': 'Informe uma data válida no formato dd/mm/aaaa.',
            },
            'valor_cobrado': {
                'required': 'Informe o valor cobrado.',
                'invalid': 'Informe um valor numérico válido (ex.: 180.00).',
                'max_digits': 'O valor cobrado é grande demais.',
                'max_decimal_places': 'Use no máximo 2 casas decimais no valor cobrado.',
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['data_entrega'].input_formats = ['%d/%m/%Y']

        custos = list(CustoProduto.objects.order_by('produto', 'sabor'))
        choices = [('', 'Selecione o produto e o sabor')]
        for custo in custos:
            choices.append(
                (str(custo.pk), f'{custo.produto} ({custo.sabor})')
            )
        choices.append((ITEM_OUTRO, 'Outro (informar manualmente)'))
        self.fields['item'].choices = choices

        if self.instance and self.instance.pk and not self.is_bound:
            self.fields['cliente'].initial = self.instance.cliente.nome
            custo_atual = next(
                (
                    custo
                    for custo in custos
                    if custo.produto == self.instance.produto
                    and custo.sabor == self.instance.sabor
                ),
                None,
            )
            if custo_atual is not None:
                self.fields['item'].initial = str(custo_atual.pk)
            else:
                self.fields['item'].initial = ITEM_OUTRO
                self.fields['produto_outro'].initial = self.instance.produto
                self.fields['sabor_outro'].initial = self.instance.sabor

        for name, field in self.fields.items():
            if name not in {'produto_outro', 'sabor_outro'}:
                field.required = True
            css = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{css} input'.strip()
            if self.is_bound and name in self.errors:
                field.widget.attrs['aria-invalid'] = 'true'

        self.fields['item'].widget.attrs['id'] = 'id_item'
        self.fields['produto_outro'].widget.attrs['data-outro-field'] = '1'
        self.fields['sabor_outro'].widget.attrs['data-outro-field'] = '1'

    def clean_cliente(self):
        nome = self.cleaned_data['cliente'].strip()
        if not nome:
            raise forms.ValidationError(
                'Informe o nome do cliente.',
                code='required',
            )
        return nome

    def clean(self):
        cleaned_data = super().clean()
        item = cleaned_data.get('item')

        if item == ITEM_OUTRO:
            produto = (cleaned_data.get('produto_outro') or '').strip()
            sabor = (cleaned_data.get('sabor_outro') or '').strip()
            if not produto:
                self.add_error(
                    'produto_outro',
                    forms.ValidationError(
                        'Informe o produto.',
                        code='required',
                    ),
                )
            if not sabor:
                self.add_error(
                    'sabor_outro',
                    forms.ValidationError(
                        'Informe o sabor.',
                        code='required',
                    ),
                )
            cleaned_data['produto'] = produto
            cleaned_data['sabor'] = sabor
            cleaned_data['produto_outro'] = produto
            cleaned_data['sabor_outro'] = sabor
        elif item:
            try:
                custo = CustoProduto.objects.get(pk=item)
            except (CustoProduto.DoesNotExist, ValueError, TypeError):
                self.add_error(
                    'item',
                    forms.ValidationError(
                        'Selecione uma opção válida de produto e sabor.',
                        code='invalid_choice',
                    ),
                )
            else:
                cleaned_data['produto'] = custo.produto
                cleaned_data['sabor'] = custo.sabor

        return cleaned_data

    def save(self, commit=True):
        status_atual = self.instance.status if self.instance.pk else None
        encomenda = super().save(commit=False)
        encomenda.produto = self.cleaned_data['produto']
        encomenda.sabor = self.cleaned_data['sabor']
        nome = self.cleaned_data['cliente']
        cliente = Cliente.objects.filter(nome__iexact=nome).first()
        if cliente is None:
            cliente = Cliente.objects.create(nome=nome, telefone='')
        encomenda.cliente = cliente
        if status_atual is not None:
            encomenda.status = status_atual
        if commit:
            encomenda.save()
        return encomenda


class CustoProdutoForm(forms.ModelForm):
    class Meta:
        model = CustoProduto
        fields = ['produto', 'sabor', 'custo_producao']
        labels = {
            'produto': 'Produto',
            'sabor': 'Sabor',
            'custo_producao': 'Custo de produção',
        }
        widgets = {
            'produto': forms.TextInput(attrs={'placeholder': 'Bolo'}),
            'sabor': forms.TextInput(attrs={'placeholder': 'Chocolate'}),
            'custo_producao': forms.NumberInput(
                attrs={
                    'placeholder': '0,00',
                    'step': '0.01',
                    'min': '0.01',
                    'inputmode': 'decimal',
                }
            ),
        }
        error_messages = {
            'produto': {
                'required': 'Informe o produto.',
            },
            'sabor': {
                'required': 'Informe o sabor.',
            },
            'custo_producao': {
                'required': 'Informe o custo de produção.',
                'invalid': 'Informe um valor numérico válido (ex.: 85.00).',
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.created = False
        for name, field in self.fields.items():
            field.required = True
            css = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{css} input'.strip()
            if self.is_bound and name in self.errors:
                field.widget.attrs['aria-invalid'] = 'true'

    def clean_produto(self):
        produto = self.cleaned_data['produto'].strip()
        if not produto:
            raise forms.ValidationError(
                'Informe o produto.',
                code='required',
            )
        return produto

    def clean_sabor(self):
        sabor = self.cleaned_data['sabor'].strip()
        if not sabor:
            raise forms.ValidationError(
                'Informe o sabor.',
                code='required',
            )
        return sabor

    def clean_custo_producao(self):
        custo = self.cleaned_data['custo_producao']
        if custo is None:
            raise forms.ValidationError(
                'Informe o custo de produção.',
                code='required',
            )
        if custo <= Decimal('0'):
            raise forms.ValidationError(
                'Informe um valor numérico positivo para o custo de produção.',
                code='invalid',
            )
        return custo

    def validate_unique(self):
        # produto+sabor pode já existir: save() atualiza em vez de duplicar.
        return

    def save(self, commit=True):
        produto = self.cleaned_data['produto']
        sabor = self.cleaned_data['sabor']
        custo_producao = self.cleaned_data['custo_producao']
        custo, created = CustoProduto.objects.update_or_create(
            produto=produto,
            sabor=sabor,
            defaults={'custo_producao': custo_producao},
        )
        self.created = created
        return custo

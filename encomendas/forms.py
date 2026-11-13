from decimal import Decimal

from django import forms

from .models import Cliente, CustoProduto, Encomenda


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

    class Meta:
        model = Encomenda
        fields = ['produto', 'sabor', 'data_entrega', 'valor_cobrado']
        labels = {
            'produto': 'Produto',
            'sabor': 'Sabor',
            'data_entrega': 'Data de entrega',
            'valor_cobrado': 'Valor cobrado',
        }
        widgets = {
            'produto': forms.TextInput(attrs={'placeholder': 'Bolo'}),
            'sabor': forms.TextInput(attrs={'placeholder': 'Chocolate'}),
            'data_entrega': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'type': 'date'},
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
            'produto': {
                'required': 'Informe o produto.',
            },
            'sabor': {
                'required': 'Informe o sabor.',
            },
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
        for name, field in self.fields.items():
            field.required = True
            css = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{css} input'.strip()
            if self.is_bound and name in self.errors:
                field.widget.attrs['aria-invalid'] = 'true'

    def clean_cliente(self):
        nome = self.cleaned_data['cliente'].strip()
        if not nome:
            raise forms.ValidationError(
                'Informe o nome do cliente.',
                code='required',
            )
        return nome

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

    def save(self, commit=True):
        encomenda = super().save(commit=False)
        nome = self.cleaned_data['cliente']
        cliente = Cliente.objects.filter(nome__iexact=nome).first()
        if cliente is None:
            cliente = Cliente.objects.create(nome=nome, telefone='')
        encomenda.cliente = cliente
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

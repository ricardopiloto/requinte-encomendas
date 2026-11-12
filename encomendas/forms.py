from django import forms

from .models import Cliente, Encomenda


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

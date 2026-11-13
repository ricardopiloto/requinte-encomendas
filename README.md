# Requinte Encomendas

Aplicação web para controle de encomendas de um ateliê de doces (Ateliê do Requinte).

## Problema que resolve

Em um ateliê de doces, pedidos chegam por WhatsApp, telefone ou balcão, e o controle costuma ficar espalhado em anotações soltas. Isso dificulta:

- saber **o que** precisa ser produzido e **para quando**;
- acompanhar o **status** de cada encomenda (pendente, em produção, entregue);
- entender a **margem** de cada pedido (valor cobrado versus custo de produção).

Este projeto concentra esse fluxo em uma ferramenta simples, com login obrigatório: cadastrar encomendas, listá-las com filtro por status e visualizar a margem com base nos custos cadastrados por produto e sabor.

## Arquitetura (MVT)

O projeto segue o padrão **MVT** do Django:

| Camada | Papel neste projeto |
|--------|---------------------|
| **Model** | Dados persistidos (`Cliente`, `Encomenda`, `CustoProduto`) em `encomendas/models.py` |
| **View** | Regras de tela e fluxo HTTP em `encomendas/views.py` (menu, cadastro, listagem) |
| **Template** | HTML das telas em `encomendas/templates/` |

O formulário de cadastro (`EncomendaForm`) fica em `encomendas/forms.py` e valida os campos no backend antes de salvar.

## Stack

- **Python 3**
- **Django 5.2**
- **SQLite** (banco padrão em desenvolvimento)
- **django-axes** (limite de tentativas de login)

## Estrutura principal

```text
requinte-encomendas/
├── manage.py
├── requirements.txt
├── requinte/          # configuração do projeto (settings, urls)
└── encomendas/        # app principal (models, views, forms, templates, tests)
```

## Instalação e execução local

### 1. Clonar o repositório e entrar na pasta

```bash
cd requinte-encomendas
```

### 2. Criar e ativar o ambiente virtual

```bash
python3 -m venv venv
source venv/bin/activate
```

No Windows (PowerShell):

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Instalar as dependências

```bash
pip install -r requirements.txt
```

### 4. Aplicar as migrations

```bash
python manage.py migrate
```

### 5. Criar um usuário para acessar o sistema

```bash
python manage.py createsuperuser
```

Informe username e senha quando solicitado.

### 6. Subir o servidor de desenvolvimento

```bash
python manage.py runserver
```

Acesse:

- App: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- Login: [http://127.0.0.1:8000/login/](http://127.0.0.1:8000/login/)
- Admin: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

## Telas

1. **Menu inicial** (`/`) — Nova encomenda, Minhas encomendas, Custos de produtos
2. **Nova encomenda** (`/encomendas/nova/`) — formulário de cadastro
3. **Minhas encomendas** (`/encomendas/`) — listagem com filtro por status, margem e paginação

## Testes

Os testes do app `encomendas` cobrem:

- cálculo da margem (`valor_cobrado - custo_producao`);
- validação do formulário de encomenda;
- valores válidos/inválidos do campo `status`;
- fluxo de integração: login → cadastro via POST → listagem com status e margem.

Para executar todos os testes:

```bash
python manage.py test
```

Apenas o app `encomendas`:

```bash
python manage.py test encomendas
```

Com mais detalhes:

```bash
python manage.py test encomendas -v 2
```

## Licença

Veja o arquivo [LICENSE](LICENSE).

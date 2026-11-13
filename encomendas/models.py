from django.db import models


class Cliente(models.Model):
    nome = models.CharField(max_length=200)
    telefone = models.CharField(max_length=20)
    observacoes = models.TextField(blank=True)

    def __str__(self):
        return self.nome


class Encomenda(models.Model):
    class Status(models.TextChoices):
        PENDENTE = 'pendente', 'Pendente'
        EM_PRODUCAO = 'em_producao', 'Em produção'
        ENTREGUE = 'entregue', 'Entregue'

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='encomendas',
    )
    produto = models.CharField(max_length=200)
    sabor = models.CharField(max_length=200)
    data_entrega = models.DateField(db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDENTE,
    )
    valor_cobrado = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f'{self.produto} ({self.sabor}) — {self.cliente.nome}'


class CustoProduto(models.Model):
    produto = models.CharField(max_length=200)
    sabor = models.CharField(max_length=200)
    custo_producao = models.DecimalField(max_digits=10, decimal_places=2)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('produto', 'sabor')]

    def __str__(self):
        return f'{self.produto} ({self.sabor})'

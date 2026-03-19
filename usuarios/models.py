from django.db import models
from django.contrib.auth.models import User
from martor.models import MartorField

class Cliente(models.Model):
    # a classe model esencial para criar a tabela no banco de dados, 
    # e os campos são definidos como atributos da classe. O campo user é uma 
    # chave estrangeira que se relaciona com o modelo User do Django, 
    # permitindo associar cada cliente a um usuário específico.

    TIPO_CHOICES = [
        ('PF', 'Pessoa Física'),
        ('PJ', 'Pessoa Jurídica'),
    ]
    nome = models.CharField(max_length=255)
    email = models.EmailField(max_length=255)
    tipo = models.CharField(max_length=2, choices=TIPO_CHOICES, default='PF')
    status = models.BooleanField(default=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    # o campo user é uma chave estrangeira que se relaciona com o modelo User do Django, 
    # permitindo associar cada cliente a um usuário específico. O parâmetro on_delete=models.CASCADE

    def __str__(self):
        return self.nome


class Documentos(models.Model):
    TIPO_CHOICES = [
        ('C', 'Contrato'),
        ('P', 'Petição'),
        ('CONT', 'Contestação'),
        ('R', 'Recursos'),
        ('O', 'Outro'),
    ]
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=255, choices=TIPO_CHOICES, default='O')
    arquivo = models.FileField(upload_to='documentos/')
    data_upload = models.DateTimeField()
    content = MartorField()
    # transcrição do conteúdo do documento, usando o campo MartorField para armazenar o texto transcrito.

    def __str__(self):
        return self.tipo

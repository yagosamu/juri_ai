from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from martor.models import MartorField
from cryptography.fernet import Fernet
from auditlog.registry import auditlog


# ── Choices de tribunal derivados do TribunalLiteral (ia/literals.py) ──────────
TRIBUNAL_CHOICES = [
    # Superiores
    ('tst',    'TST — Tribunal Superior do Trabalho'),
    ('tse',    'TSE — Tribunal Superior Eleitoral'),
    ('stj',    'STJ — Superior Tribunal de Justiça'),
    ('stm',    'STM — Superior Tribunal Militar'),
    # TRFs
    ('trf1',   'TRF-1ª Região'),
    ('trf2',   'TRF-2ª Região'),
    ('trf3',   'TRF-3ª Região'),
    ('trf4',   'TRF-4ª Região'),
    ('trf5',   'TRF-5ª Região'),
    ('trf6',   'TRF-6ª Região'),
    # Tribunais de Justiça
    ('tjac',   'TJAC — Acre'),
    ('tjal',   'TJAL — Alagoas'),
    ('tjam',   'TJAM — Amazonas'),
    ('tjap',   'TJAP — Amapá'),
    ('tjba',   'TJBA — Bahia'),
    ('tjce',   'TJCE — Ceará'),
    ('tjdft',  'TJDFT — Distrito Federal'),
    ('tjes',   'TJES — Espírito Santo'),
    ('tjgo',   'TJGO — Goiás'),
    ('tjma',   'TJMA — Maranhão'),
    ('tjmg',   'TJMG — Minas Gerais'),
    ('tjms',   'TJMS — Mato Grosso do Sul'),
    ('tjmt',   'TJMT — Mato Grosso'),
    ('tjpa',   'TJPA — Pará'),
    ('tjpb',   'TJPB — Paraíba'),
    ('tjpe',   'TJPE — Pernambuco'),
    ('tjpi',   'TJPI — Piauí'),
    ('tjpr',   'TJPR — Paraná'),
    ('tjrj',   'TJRJ — Rio de Janeiro'),
    ('tjrn',   'TJRN — Rio Grande do Norte'),
    ('tjro',   'TJRO — Rondônia'),
    ('tjrr',   'TJRR — Roraima'),
    ('tjrs',   'TJRS — Rio Grande do Sul'),
    ('tjsc',   'TJSC — Santa Catarina'),
    ('tjse',   'TJSE — Sergipe'),
    ('tjsp',   'TJSP — São Paulo'),
    ('tjto',   'TJTO — Tocantins'),
    # TRTs
    ('trt1',   'TRT-1ª Região'),
    ('trt2',   'TRT-2ª Região'),
    ('trt3',   'TRT-3ª Região'),
    ('trt4',   'TRT-4ª Região'),
    ('trt5',   'TRT-5ª Região'),
    ('trt6',   'TRT-6ª Região'),
    ('trt7',   'TRT-7ª Região'),
    ('trt8',   'TRT-8ª Região'),
    ('trt9',   'TRT-9ª Região'),
    ('trt10',  'TRT-10ª Região'),
    ('trt11',  'TRT-11ª Região'),
    ('trt12',  'TRT-12ª Região'),
    ('trt13',  'TRT-13ª Região'),
    ('trt14',  'TRT-14ª Região'),
    ('trt15',  'TRT-15ª Região'),
    ('trt16',  'TRT-16ª Região'),
    ('trt17',  'TRT-17ª Região'),
    ('trt18',  'TRT-18ª Região'),
    ('trt19',  'TRT-19ª Região'),
    ('trt20',  'TRT-20ª Região'),
    ('trt21',  'TRT-21ª Região'),
    ('trt22',  'TRT-22ª Região'),
    ('trt23',  'TRT-23ª Região'),
    ('trt24',  'TRT-24ª Região'),
    # TREs
    ('tre-ac', 'TRE-AC — Acre'),
    ('tre-al', 'TRE-AL — Alagoas'),
    ('tre-am', 'TRE-AM — Amazonas'),
    ('tre-ap', 'TRE-AP — Amapá'),
    ('tre-ba', 'TRE-BA — Bahia'),
    ('tre-ce', 'TRE-CE — Ceará'),
    ('tre-dft','TRE-DF — Distrito Federal'),
    ('tre-es', 'TRE-ES — Espírito Santo'),
    ('tre-go', 'TRE-GO — Goiás'),
    ('tre-ma', 'TRE-MA — Maranhão'),
    ('tre-mg', 'TRE-MG — Minas Gerais'),
    ('tre-ms', 'TRE-MS — Mato Grosso do Sul'),
    ('tre-mt', 'TRE-MT — Mato Grosso'),
    ('tre-pa', 'TRE-PA — Pará'),
    ('tre-pb', 'TRE-PB — Paraíba'),
    ('tre-pe', 'TRE-PE — Pernambuco'),
    ('tre-pi', 'TRE-PI — Piauí'),
    ('tre-pr', 'TRE-PR — Paraná'),
    ('tre-rj', 'TRE-RJ — Rio de Janeiro'),
    ('tre-rn', 'TRE-RN — Rio Grande do Norte'),
    ('tre-ro', 'TRE-RO — Rondônia'),
    ('tre-rr', 'TRE-RR — Roraima'),
    ('tre-rs', 'TRE-RS — Rio Grande do Sul'),
    ('tre-sc', 'TRE-SC — Santa Catarina'),
    ('tre-se', 'TRE-SE — Sergipe'),
    ('tre-sp', 'TRE-SP — São Paulo'),
    ('tre-to', 'TRE-TO — Tocantins'),
    # Militares estaduais
    ('tjmmg',  'TJM-MG — Tribunal de Justiça Militar de Minas Gerais'),
    ('tjmrs',  'TJM-RS — Tribunal de Justiça Militar do Rio Grande do Sul'),
    ('tjmsp',  'TJM-SP — Tribunal de Justiça Militar de São Paulo'),
    # Outros
    ('outro',  'Outro'),
]


class EncryptedCharField(models.TextField):
    """Armazena valor criptografado com Fernet. Requer FIELD_ENCRYPTION_KEY no .env"""

    def _cipher(self):
        return Fernet(settings.FIELD_ENCRYPTION_KEY.encode())

    def from_db_value(self, value, expression, connection):
        if value:
            return self._cipher().decrypt(value.encode()).decode()
        return value

    def get_prep_value(self, value):
        if value:
            return self._cipher().encrypt(value.encode()).decode()
        return value

class Processo(models.Model):

    STATUS_CHOICES = [
        ('ativo',     'Ativo'),
        ('suspenso',  'Suspenso'),
        ('arquivado', 'Arquivado'),
    ]

    numero_cnj        = models.CharField(max_length=30, verbose_name='Número CNJ')
    tribunal          = models.CharField(max_length=20, choices=TRIBUNAL_CHOICES, verbose_name='Tribunal')
    tribunal_outro    = models.CharField(max_length=100, blank=True, verbose_name='Tribunal (outro)',
                                         help_text='Preencha apenas se selecionou "Outro" acima.')
    vara              = models.CharField(max_length=150, blank=True, verbose_name='Vara')
    comarca           = models.CharField(max_length=150, blank=True, verbose_name='Comarca')
    tipo_acao         = models.CharField(max_length=150, blank=True, verbose_name='Tipo de ação')
    polo_ativo        = models.CharField(max_length=255, blank=True, verbose_name='Polo ativo')
    polo_passivo      = models.CharField(max_length=255, blank=True, verbose_name='Polo passivo')
    status            = models.CharField(max_length=15, choices=STATUS_CHOICES, default='ativo',
                                         verbose_name='Status')
    data_distribuicao = models.DateField(null=True, blank=True, verbose_name='Data de distribuição')
    valor_causa       = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                            verbose_name='Valor da causa (R$)')

    cliente           = models.ForeignKey('Cliente', on_delete=models.CASCADE, related_name='processos')
    user              = models.ForeignKey(User, on_delete=models.CASCADE, related_name='processos')

    criado_em         = models.DateTimeField(auto_now_add=True)
    atualizado_em     = models.DateTimeField(auto_now=True)
    ultima_consulta_datajud = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Última consulta DataJud',
    )

    class Meta:
        ordering = ['-criado_em']
        unique_together = ('numero_cnj', 'user')
        verbose_name = 'Processo'
        verbose_name_plural = 'Processos'

    def __str__(self):
        n = self.numero_cnj.replace('-', '').replace('.', '')
        if len(n) == 20:
            return f"{n[:7]}-{n[7:9]}.{n[9:13]}.{n[13]}.{n[14:16]}.{n[16:]}"
        return self.numero_cnj

    def get_tribunal_display_completo(self):
        """Retorna o label do tribunal, ou o campo livre se for 'outro'."""
        if self.tribunal == 'outro' and self.tribunal_outro:
            return self.tribunal_outro
        return self.get_tribunal_display()


class AndamentoProcesso(models.Model):
    FONTE_CHOICES = [
        ('datajud', 'DataJud'),
        ('manual',  'Manual'),
    ]

    processo       = models.ForeignKey(Processo, on_delete=models.CASCADE,
                                       related_name='andamentos')
    data           = models.DateField(verbose_name='Data', db_index=True)
    descricao      = models.TextField(verbose_name='Descrição')
    tipo           = models.CharField(max_length=200, blank=True, verbose_name='Tipo')
    codigo_datajud = models.IntegerField(null=True, blank=True,
                                         verbose_name='Código DataJud')
    fonte          = models.CharField(max_length=10, choices=FONTE_CHOICES,
                                      default='datajud', verbose_name='Fonte')
    criado_em      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data', '-criado_em']
        verbose_name = 'Andamento'
        verbose_name_plural = 'Andamentos'

    def __str__(self):
        return f"{self.data} — {self.descricao[:60]}"


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
    cliente  = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    processo = models.ForeignKey('Processo', on_delete=models.SET_NULL,
                                  null=True, blank=True, related_name='documentos')
    tipo = models.CharField(max_length=255, choices=TIPO_CHOICES, default='O')
    arquivo = models.FileField(upload_to='documentos/')
    data_upload = models.DateTimeField()
    content = MartorField()
    # transcrição do conteúdo do documento, usando o campo MartorField para armazenar o texto transcrito.

    def __str__(self):
        return self.tipo


class ConfiguracaoWhatsApp(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='configuracao_whatsapp')
    base_url = models.URLField(help_text="URL do servidor Evolution API (ex: http://meuservidor.com)")
    api_key = EncryptedCharField(help_text="API Key da instância Evolution API")
    instancia = models.CharField(max_length=100, help_text="Nome da instância no Evolution API")

    def __str__(self):
        return f"WhatsApp — {self.user.username}"


class ConsentimentoLGPD(models.Model):
    """Registra data, versão e IP do consentimento LGPD obtido no cadastro."""
    user      = models.OneToOneField(User, on_delete=models.CASCADE, related_name='consentimento')
    aceito_em = models.DateTimeField(auto_now_add=True)
    versao    = models.CharField(max_length=10, default='1.0')
    ip        = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"Consentimento — {self.user.username} ({self.aceito_em.date()})"


class Prazo(models.Model):
    TIPO_CHOICES = [
        ('audiencia',  'Audiência'),
        ('protocolo',  'Protocolo'),
        ('recurso',    'Recurso'),
        ('diligencia', 'Diligência'),
        ('outro',      'Outro'),
    ]
    STATUS_CHOICES = [
        ('pendente',  'Pendente'),
        ('concluido', 'Concluído'),
        ('cancelado', 'Cancelado'),
    ]

    descricao         = models.CharField(max_length=255, verbose_name='Descrição')
    data_prazo        = models.DateField(db_index=True, verbose_name='Data do prazo')
    tipo              = models.CharField(max_length=20, choices=TIPO_CHOICES, verbose_name='Tipo')
    processo          = models.ForeignKey(Processo, on_delete=models.CASCADE,
                                          related_name='prazos', verbose_name='Processo')
    alerta_dias_antes = models.PositiveSmallIntegerField(default=3,
                                                          verbose_name='Alertar X dias antes')
    status            = models.CharField(max_length=15, choices=STATUS_CHOICES,
                                         default='pendente', verbose_name='Status')
    google_event_id   = models.CharField(max_length=255, blank=True,
                                          verbose_name='ID do evento no Google Calendar')
    user              = models.ForeignKey(User, on_delete=models.CASCADE,
                                          related_name='prazos', verbose_name='Advogado')
    criado_em         = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['data_prazo']
        verbose_name = 'Prazo'
        verbose_name_plural = 'Prazos'

    def __str__(self):
        data = self.data_prazo
        data_str = data.strftime('%d/%m/%Y') if hasattr(data, 'strftime') else data
        return f"{self.get_tipo_display()} — {self.descricao} ({data_str})"


auditlog.register(Processo)
auditlog.register(AndamentoProcesso)
auditlog.register(Prazo)
auditlog.register(Cliente)
auditlog.register(Documentos)
auditlog.register(ConfiguracaoWhatsApp)
auditlog.register(User)

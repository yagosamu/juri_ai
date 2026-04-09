import datetime
from collections import defaultdict
from django.utils import timezone
from django.shortcuts import get_object_or_404
from usuarios.models import Documentos
from .agents import JuriAI

def ocr_and_markdown_file(instance_id):
    from docling.document_converter import DocumentConverter
    import os

    documentos = get_object_or_404(Documentos, id=instance_id)

    if not os.path.exists(documentos.arquivo.path):
        return f'Arquivo não encontrado: {documentos.arquivo.path}'

    converter = DocumentConverter()
    result = converter.convert(documentos.arquivo.path)
    doc = result.document
    texto = doc.export_to_markdown()

    documentos.content = texto
    documentos.save()
    return 'Ok'


def rag_documentos(instance_id):
    documentos = get_object_or_404(Documentos, id=instance_id)
    JuriAI.knowledge.insert(
        name=documentos.arquivo.name,
        text_content=documentos.content,
        metadata={
            "cliente_id": documentos.cliente.id,
            "name": documentos.arquivo.name,
        },
    )


def enviar_alertas_prazos():
    """
    Task diária (agendada no django-q às 8h).
    Envia e-mail para cada advogado com prazos cujo alerta está vencendo hoje.
    Um prazo entra na lista quando: hoje == data_prazo - alerta_dias_antes.
    Ou seja, o alerta é disparado exatamente uma vez, no dia certo.
    """
    from django.core.mail import send_mail
    from django.conf import settings as django_settings
    from usuarios.models import Prazo

    hoje = datetime.date.today()

    prazos_pendentes = (
        Prazo.objects
        .filter(status='pendente')
        .select_related('user', 'processo', 'processo__cliente')
    )

    alertas_por_usuario = defaultdict(list)
    for prazo in prazos_pendentes:
        dias_restantes = (prazo.data_prazo - hoje).days
        if 0 <= dias_restantes <= prazo.alerta_dias_antes:
            alertas_por_usuario[prazo.user].append((prazo, dias_restantes))

    for user, lista in alertas_por_usuario.items():
        if not user.email:
            continue

        linhas = []
        for prazo, dias in lista:
            if dias == 0:
                urgencia = 'HOJE'
            elif dias == 1:
                urgencia = 'AMANHÃ'
            else:
                urgencia = f'em {dias} dias'
            linhas.append(
                f'• [{prazo.get_tipo_display()}] {prazo.descricao}'
                f' — Processo {prazo.processo}'
                f' — Vence {urgencia} ({prazo.data_prazo.strftime("%d/%m/%Y")})'
            )

        corpo = (
            f'Olá, {user.first_name or user.username}!\n\n'
            f'Você tem {len(lista)} prazo(s) próximo(s):\n\n'
            + '\n'.join(linhas)
            + '\n\nAcesse o JuriAI para mais detalhes.\n'
        )

        try:
            send_mail(
                subject=f'JuriAI — {len(lista)} prazo(s) próximo(s)',
                message=corpo,
                from_email=django_settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception:
            pass


def consultar_datajud(processo_id):
    """Busca movimentos no DataJud e persiste apenas os novos."""
    import requests
    from usuarios.models import Processo, AndamentoProcesso

    proc = Processo.objects.filter(id=processo_id).first()
    if not proc or proc.tribunal == 'outro':
        return 'Tribunal inválido ou não selecionado'

    numero = proc.numero_cnj.replace('-', '').replace('.', '')
    url = f"https://api-publica.datajud.cnj.jus.br/api_publica_{proc.tribunal}/_search"
    headers = {
        'Authorization': 'APIKey cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw==',
        'Content-Type': 'application/json',
    }
    try:
        resp = requests.post(
            url, headers=headers,
            json={'query': {'match': {'numeroProcesso': numero}}},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return f'Erro na API DataJud: {e}'

    hits = data.get('hits', {}).get('hits', [])
    if not hits:
        return 'Nenhum resultado encontrado no DataJud'

    movimentos = hits[0].get('_source', {}).get('movimentos', [])
    novos = 0
    for mov in movimentos:
        try:
            data_mov = datetime.date.fromisoformat(mov.get('dataHora', '')[:10])
        except (KeyError, ValueError, TypeError):
            continue
        codigo = mov.get('codigo')
        if not AndamentoProcesso.objects.filter(
            processo=proc, data=data_mov, codigo_datajud=codigo
        ).exists():
            AndamentoProcesso.objects.create(
                processo=proc,
                data=data_mov,
                descricao=mov.get('nome', ''),
                tipo=mov.get('nome', ''),
                codigo_datajud=codigo,
                fonte='datajud',
            )
            novos += 1

    Processo.objects.filter(id=processo_id).update(
        ultima_consulta_datajud=timezone.now()
    )
    return f'{novos} andamento(s) novo(s) importado(s)'


def alertar_honorarios_atrasados():
    """
    Task diária — notifica o advogado via WhatsApp sobre honorários em atraso.
    Silenciosa se ConfiguracaoWhatsApp não configurada ou telefone_advogado vazio.
    """
    import datetime
    from collections import defaultdict
    from usuarios.models import Honorario, ConfiguracaoWhatsApp

    hoje = datetime.date.today()

    atrasados = (
        Honorario.objects
        .filter(status='pendente', vencimento__lt=hoje)
        .select_related('user', 'cliente')
    )

    por_usuario = defaultdict(list)
    for h in atrasados:
        por_usuario[h.user].append(h)

    for user, lista in por_usuario.items():
        try:
            config = ConfiguracaoWhatsApp.objects.get(user=user)
            if not config.telefone_advogado:
                continue
        except ConfiguracaoWhatsApp.DoesNotExist:
            continue

        linhas = []
        for h in lista:
            dias   = (hoje - h.vencimento).days
            sufixo = 'dia' if dias == 1 else 'dias'
            linhas.append(
                f'• {h.cliente.nome} — R$ {h.valor_total} '
                f'(venceu há {dias} {sufixo})'
            )

        mensagem = (
            f'⚠️ JuriAI — {len(lista)} honorário(s) em atraso:\n\n'
            + '\n'.join(linhas)
            + '\n\nAcesse o sistema para regularizar.'
        )

        try:
            from ia.wrapper_evolution_api import SendMessage
            api = SendMessage(base_url=config.base_url, api_key=config.api_key)
            api.send_message(
                instance=config.instancia,
                body={'number': config.telefone_advogado, 'text': mensagem},
            )
        except Exception:
            pass


def atualizar_todos_processos_datajud():
    """Schedule diário — dispara consultar_datajud para cada processo ativo."""
    from django_q.tasks import async_task
    from usuarios.models import Processo

    for proc in Processo.objects.filter(status='ativo').exclude(tribunal='outro'):
        async_task('ia.tasks.consultar_datajud', proc.id)
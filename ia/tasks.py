import datetime
from collections import defaultdict
from django.shortcuts import get_object_or_404
from usuarios.models import Documentos
from .agents import JuriAI

def ocr_and_markdown_file(instance_id):
    from docling.document_converter import DocumentConverter

    documentos = get_object_or_404(Documentos, id=instance_id)

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
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max
from django.views.decorators.csrf import csrf_exempt
from usuarios.models import (ConfiguracaoWhatsApp, Cliente, Documentos,
                              Processo, Honorario, TemplateDocumento, DocumentoGerado,
                              Lead)
from mpire import context
from semchunk.semchunk import chunk
from ia.models import Pergunta
from .models import ContextRag, Pergunta, AnaliseJurisprudencia
from django.http import JsonResponse, StreamingHttpResponse
from django.db.models import Q
from .agents import JuriAI, SecretariaAI, RedacaoAI
from typing import Iterator
from agno.agent import RunOutputEvent, RunEvent
from ia.agente_langchain import JurisprudenciaAI
from .models import AnaliseJurisprudencia
from django.contrib import messages
from django.contrib.messages import constants
import time
from agno.agent import RunOutput
import json
from .wrapper_evolution_api import SendMessage
from agno.agent import RunOutput
from .agents import SecretariaAI



@csrf_exempt
@login_required
def chat(request, id):
    cliente = get_object_or_404(Cliente, id=id, user=request.user)
    if request.method == 'GET':
        return render(request, 'chat.html', {'cliente': cliente})
    elif request.method == 'POST':
        pergunta = request.POST.get('pergunta')
        pergunta_model = Pergunta(pergunta=pergunta, cliente=cliente)
        pergunta_model.save()
        return JsonResponse({'id': pergunta_model.id})
    

@login_required
def stream_resposta(request):
    id_pergunta = request.POST.get('id_pergunta')

    pergunta = get_object_or_404(Pergunta, id=id_pergunta, cliente__user=request.user)

    def gerar_resposta():
        
        agent = JuriAI.build_agent(knowledge_filters={'cliente_id': pergunta.cliente.id})
        
        stream: Iterator[RunOutputEvent] = agent.run(pergunta.pergunta, stream=True, stream_events=True)
        for chunk in stream:
            if chunk.event == RunEvent.run_content:
                yield str(chunk.content)
            if chunk.event == RunEvent.tool_call_completed:
                context = ContextRag(content=chunk.tool.result, tool_name=chunk.tool.tool_name, tool_args=chunk.tool.tool_args, pergunta=pergunta)
                context.save()

    response = StreamingHttpResponse(
        gerar_resposta(),
        content_type='text/plain; charset=utf-8'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    
    return response


@login_required
def ver_referencias(request, id):
    pergunta = get_object_or_404(Pergunta, id=id, cliente__user=request.user)
    contextos = ContextRag.objects.filter(pergunta=pergunta)
    return render(request, 'ver_referencias.html', {
        'pergunta': pergunta,
        'contextos': contextos
    })


@login_required
def analise_jurisprudencia(request, id):
    documento = get_object_or_404(Documentos, id=id, cliente__user=request.user)
    analise = AnaliseJurisprudencia.objects.filter(documento=documento).first()
    return render(request, 'analise_jurisprudencia.html', {
        'documento': documento,
        'analise': analise
    })


@login_required
def processar_analise(request, id):
    if request.method != 'POST':
        messages.add_message(request, constants.ERROR, 'Método não permitido.')
        return redirect('analise_jurisprudencia', id=id)
    
    try:
        documento = get_object_or_404(Documentos, id=id, cliente__user=request.user)
        start_time = time.time()
        
        agent = JurisprudenciaAI()
        response = agent.run(documento.content)
        
        processing_time = int(time.time() - start_time)
        
        indice = response.indice_risco
        if indice <= 30:
            classificacao = "Baixo"
        elif indice <= 60:
            classificacao = "Médio"
        elif indice <= 80:
            classificacao = "Alto"
        else:
            classificacao = "Crítico"
        
        analise, created = AnaliseJurisprudencia.objects.update_or_create(
            documento=documento,
            defaults={
                'indice_risco': indice,
                'classificacao': classificacao,
                'erros_coerencia': response.erros_coerencia,
                'riscos_juridicos': response.riscos_juridicos,
                'problemas_formatacao': response.problemas_formatacao,
                'red_flags': response.red_flags,
                'tempo_processamento': processing_time
            }
        )
        
        if created:
            messages.add_message(request, constants.SUCCESS, 'Análise realizada e salva com sucesso!')
        else:
            messages.add_message(request, constants.SUCCESS, 'Análise atualizada com sucesso!')
        
        return redirect('analise_jurisprudencia', id=id)
    except Exception as e:
        messages.add_message(request, constants.ERROR, f'Erro ao processar análise: {str(e)}')
        return redirect('analise_jurisprudencia', id=id)


@login_required
def lista_chats(request):
    clientes = (Cliente.objects
                .filter(user=request.user, pergunta__isnull=False)
                .annotate(
                    total_perguntas=Count('pergunta'),
                    ultima_pergunta_id=Max('pergunta__id'),
                )
                .distinct()
                .order_by('-ultima_pergunta_id'))
    return render(request, 'lista_chats.html', {'clientes': clientes})


@login_required
def lista_analises(request):
    analises = (AnaliseJurisprudencia.objects
                .filter(documento__cliente__user=request.user)
                .select_related('documento', 'documento__cliente')
                .order_by('-data_criacao'))
    return render(request, 'lista_analises.html', {'analises': analises})


@csrf_exempt
def webhook_whatsapp(request):
    data = json.loads(request.body)
    instancia = data.get('instance')
    phone = data.get('data').get('key').get('remoteJid').split('@')[0]
    message = data.get('data').get('message').get('extendedTextMessage').get('text')

    config = get_object_or_404(ConfiguracaoWhatsApp, instancia=instancia)

    # Cria Lead automaticamente se o número for desconhecido
    cliente_existe = Cliente.objects.filter(user=config.user, telefone=phone).exists()
    lead_existe    = Lead.objects.filter(user=config.user, telefone=phone).exists()
    if not cliente_existe and not lead_existe:
        Lead.objects.create(
            nome=f'WhatsApp {phone}',
            telefone=phone,
            origem='whatsapp',
            status='novo',
            user=config.user,
        )

    agent = SecretariaAI.build_agent(session_id=phone)
    response: RunOutput = agent.run(message)

    SendMessage(base_url=config.base_url, api_key=config.api_key).send_message(
        config.instancia,
        {"number": phone, "textMessage": {"text": response.content}}
    )

    return JsonResponse({'response': response.content})


# ── Helper de substituição de variáveis ─────────────────────────────────────────

def _substituir_variaveis(conteudo, cliente, processo, honorario, advogado_nome):
    from datetime import date

    def _fmt_valor(v):
        return f'{v:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')

    subs = {
        '{{cliente.nome}}':     cliente.nome,
        '{{cliente.email}}':    cliente.email,
        '{{processo.numero}}':  str(processo) if processo else '[NÚMERO DO PROCESSO]',
        '{{processo.vara}}':    (processo.vara or '[VARA]') if processo else '[VARA]',
        '{{processo.comarca}}': (processo.comarca or '[COMARCA]') if processo else '[COMARCA]',
        '{{honorario.valor}}':  _fmt_valor(honorario.valor_total) if honorario else '[VALOR]',
        '{{data_hoje}}':        date.today().strftime('%d/%m/%Y'),
        '{{advogado.nome}}':    advogado_nome,
    }
    for var, val in subs.items():
        conteudo = conteudo.replace(var, val)
    return conteudo


# ── Views de geração de documentos ──────────────────────────────────────────────

@login_required
def gerar_documento(request):
    clientes  = Cliente.objects.filter(user=request.user).order_by('nome')
    templates = TemplateDocumento.objects.filter(
        Q(is_global=True) | Q(user=request.user)
    ).order_by('tipo', 'nome')
    processos = Processo.objects.filter(user=request.user).select_related('cliente')

    processos_json = {}
    for c in clientes:
        processos_json[str(c.id)] = [
            {'id': p.id, 'label': f'{p} — {p.vara or p.comarca or "sem vara"}'.strip(' —')}
            for p in processos if p.cliente_id == c.id
        ]

    if request.method == 'GET':
        return render(request, 'gerar_documento.html', {
            'clientes':       clientes,
            'templates':      templates,
            'processos_json': json.dumps(processos_json, ensure_ascii=False),
        })

    # POST → substituir variáveis + streaming
    template_id = request.POST.get('template_id')
    cliente_id  = request.POST.get('cliente_id')
    processo_id = request.POST.get('processo_id') or None
    instrucoes  = request.POST.get('instrucoes', '').strip()

    template  = get_object_or_404(TemplateDocumento, id=template_id)
    cliente   = get_object_or_404(Cliente, id=cliente_id, user=request.user)
    processo  = (get_object_or_404(Processo, id=processo_id, user=request.user)
                 if processo_id else None)
    honorario = Honorario.objects.filter(cliente=cliente).order_by('-criado_em').first()

    advogado_nome = request.user.get_full_name() or request.user.username
    conteudo_base = _substituir_variaveis(
        template.conteudo_markdown, cliente, processo, honorario, advogado_nome
    )

    prompt = (
        f"Instruções do advogado: "
        f"{instrucoes or 'Complete as lacunas com texto jurídico padrão.'}"
        f"\n\nDocumento:\n{conteudo_base}"
    )

    def stream():
        agent = RedacaoAI.build_agent()
        for chunk in agent.run(prompt, stream=True, stream_events=True):
            if chunk.event == RunEvent.run_content:
                yield str(chunk.content)

    resp = StreamingHttpResponse(stream(), content_type='text/plain; charset=utf-8')
    resp['Cache-Control']     = 'no-cache'
    resp['X-Accel-Buffering'] = 'no'
    return resp


@login_required
def salvar_documento(request):
    if request.method != 'POST':
        return redirect('gerar_documento')

    conteudo    = request.POST.get('conteudo', '').strip()
    cliente_id  = request.POST.get('cliente_id')
    processo_id = request.POST.get('processo_id') or None
    template_id = request.POST.get('template_id') or None
    instrucoes  = request.POST.get('instrucoes', '')

    cliente  = get_object_or_404(Cliente, id=cliente_id, user=request.user)
    processo = (get_object_or_404(Processo, id=processo_id, user=request.user)
                if processo_id else None)
    template = TemplateDocumento.objects.filter(id=template_id).first()

    doc = DocumentoGerado.objects.create(
        template=template, conteudo=conteudo, cliente=cliente,
        processo=processo, instrucoes=instrucoes, user=request.user,
    )
    return redirect('editar_documento', id=doc.id)


@login_required
def editar_documento(request, id):
    doc = get_object_or_404(DocumentoGerado, id=id, user=request.user)

    if request.method == 'POST':
        doc.conteudo = request.POST.get('conteudo', doc.conteudo)
        doc.save()
        messages.add_message(request, constants.SUCCESS, 'Documento salvo.')
        return redirect('editar_documento', id=id)

    return render(request, 'editar_documento.html', {'doc': doc})


@login_required
def exportar_documento(request, id):
    if request.method != 'POST':
        return redirect('editar_documento', id=id)

    doc     = get_object_or_404(DocumentoGerado, id=id, user=request.user)
    formato = request.POST.get('formato', 'pdf')
    nome    = f"doc_{doc.id}_{doc.cliente.nome[:30].replace(' ', '_')}"

    from .exportacao import gerar_docx, gerar_pdf
    if formato == 'docx':
        return gerar_docx(doc.conteudo, nome)
    return gerar_pdf(doc.conteudo, nome)


@login_required
def vincular_doc_gerado(request, id):
    """Cria um registro Documentos a partir do conteúdo de um DocumentoGerado."""
    if request.method != 'POST':
        return redirect('editar_documento', id=id)

    from django.core.files.base import ContentFile
    from django.utils import timezone

    doc_gerado = get_object_or_404(DocumentoGerado, id=id, user=request.user)

    tipo_map = {'contrato': 'C', 'peticao': 'P'}
    tipo     = tipo_map.get(doc_gerado.template.tipo, 'O') if doc_gerado.template else 'O'

    arquivo = ContentFile(
        doc_gerado.conteudo.encode('utf-8'),
        name=f'doc_gerado_{doc_gerado.id}.md',
    )

    Documentos.objects.create(
        cliente=doc_gerado.cliente,
        processo=doc_gerado.processo,
        tipo=tipo,
        arquivo=arquivo,
        data_upload=timezone.now(),
        content=doc_gerado.conteudo,
    )

    messages.add_message(request, constants.SUCCESS, 'Documento vinculado ao cliente.')
    return redirect('editar_documento', id=id)

from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from mpire import context
from semchunk.semchunk import chunk
from ia.models import Pergunta
from usuarios.models import Cliente
from .models import ContextRag, Pergunta
from django.http import JsonResponse, StreamingHttpResponse
from .agents import JuriAI
from typing import Iterator
from agno.agent import RunOutputEvent, RunEvent


@csrf_exempt
def chat(request, id):
    cliente = Cliente.objects.get(id=id)
    if request.method == 'GET':
        return render(request, 'chat.html', {'cliente': cliente})
    elif request.method == 'POST':
        pergunta = request.POST.get('pergunta')
        pergunta_model = Pergunta(pergunta=pergunta, cliente=cliente)
        pergunta_model.save()
        return JsonResponse({'id': pergunta_model.id})
    
def stream_resposta(request):
    id_pergunta = request.POST.get('id_pergunta')

    pergunta = get_object_or_404(Pergunta, id=id_pergunta)

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

def ver_referencias(request, id):
    pergunta = get_object_or_404(Pergunta, id=id)
    contextos = ContextRag.objects.filter(pergunta=pergunta)
    return render(request, 'ver_referencias.html', {
        'pergunta': pergunta,
        'contextos': contextos
    })

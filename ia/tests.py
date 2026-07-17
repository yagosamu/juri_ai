import os
import time
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from agno.agent import Agent
from agno.models.base import Model
from agno.models.metrics import Metrics
from agno.models.response import ModelResponse
from langchain_core.runnables import RunnableLambda
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

import ia.observability as observability
from ia.agente_langchain import JurisprudenciaAI, JurisprudenciaOutput
from ia.tasks import atualizar_indices_economicos
from ia.observability import mask_otel_spans
from usuarios.models import Cliente, TemplateDocumento


class _FailingSpanExporter(SpanExporter):
    export_calls = 0

    def export(self, spans):
        type(self).export_calls += 1
        return SpanExportResult.FAILURE

    def shutdown(self):
        pass


class _CollectingSpanExporter(SpanExporter):
    def __init__(self):
        self.spans = []
        self.export_calls = 0

    def export(self, spans):
        self.export_calls += 1
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass


class _FakeStreamingModel(Model):
    def __init__(self):
        super().__init__(id='fake-model', name='FakeModel', provider='fake')

    def invoke(self, *args, **kwargs):
        return ModelResponse(
            content='ok',
            response_usage=Metrics(input_tokens=3, output_tokens=2, total_tokens=5),
        )

    async def ainvoke(self, *args, **kwargs):
        return self.invoke(*args, **kwargs)

    def invoke_stream(self, *args, **kwargs):
        yield ModelResponse(
            content='primeiro ',
            response_usage=Metrics(input_tokens=3, output_tokens=1, total_tokens=4),
        )
        yield ModelResponse(
            content='ultimo',
            response_usage=Metrics(input_tokens=3, output_tokens=2, total_tokens=5),
        )

    async def ainvoke_stream(self, *args, **kwargs):
        for item in self.invoke_stream(*args, **kwargs):
            yield item

    def _parse_provider_response(self, response, **kwargs):
        return response

    def _parse_provider_response_delta(self, response_delta, **kwargs):
        return response_delta


class AtualizarIndicesEconomicosTaskTests(TestCase):
    @patch('usuarios.services.indices.importar_indices_bcb')
    def test_task_retorna_resumo_dos_indices_atualizados(self, mock_importar):
        mock_importar.return_value = {'selic': 1, 'tr': 0}

        resultado = atualizar_indices_economicos()

        self.assertEqual(resultado, 'Índices atualizados: selic=1')
        mock_importar.assert_called_once()

    @patch('usuarios.services.indices.importar_indices_bcb')
    def test_task_retorna_nenhum_indice_novo_quando_contadores_zerados(self, mock_importar):
        mock_importar.return_value = {'selic': 0, 'tr': 0}

        resultado = atualizar_indices_economicos()

        self.assertEqual(resultado, 'Nenhum índice novo')


class GeracaoDocumentoSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='advogado', password='abc123')
        self.outro_user = User.objects.create_user(username='outro', password='abc123')
        self.cliente = Cliente.objects.create(
            nome='Cliente Teste',
            email='cliente@example.com',
            tipo='PF',
            user=self.user,
        )
        self.template_outro_usuario = TemplateDocumento.objects.create(
            nome='Template privado de outro advogado',
            tipo='contrato',
            conteudo_markdown='Conteúdo privado',
            user=self.outro_user,
            is_global=False,
        )
        self.client.force_login(self.user)

    def test_gerar_documento_nao_aceita_template_privado_de_outro_usuario(self):
        response = self.client.post(reverse('gerar_documento'), {
            'template_id': self.template_outro_usuario.id,
            'cliente_id': self.cliente.id,
            'instrucoes': 'Gerar documento',
        })

        self.assertEqual(response.status_code, 404)


class LangfuseJurisprudenciaInstrumentationTests(TestCase):
    def tearDown(self):
        self._shutdown_langfuse_clients()

    def _shutdown_langfuse_clients(self):
        if observability._AGNO_INSTRUMENTOR is not None:
            try:
                observability._AGNO_INSTRUMENTOR.uninstrument()
            except Exception:
                pass
        observability._AGNO_INSTRUMENTOR = None
        observability._AGNO_INSTRUMENTED = False
        try:
            from langfuse._client.get_client import _create_client_from_instance
            from langfuse._client.resource_manager import LangfuseResourceManager

            for instance in list(LangfuseResourceManager._instances.values()):
                _create_client_from_instance(instance).shutdown()
            LangfuseResourceManager._instances.clear()
        except Exception:
            pass
        observability._LANGFUSE_CLIENT_INITIALIZED = False

    def _response(self):
        return JurisprudenciaOutput(
            indice_risco=12,
            erros_coerencia=[],
            riscos_juridicos=[],
            problemas_formatacao=[],
            red_flags=[],
        )

    @override_settings(LANGFUSE_ENABLED=False)
    def test_langfuse_desligado_nao_constroi_client_nem_callback(self):
        chain = Mock()
        chain.invoke.return_value = self._response()

        class TestAgent(JurisprudenciaAI):
            def _build_chain(self):
                return chain

        with patch('langfuse.Langfuse') as mock_langfuse, \
             patch('openinference.instrumentation.agno.AgnoInstrumentor') as mock_agno, \
             patch('langfuse.langchain.CallbackHandler') as mock_callback:
            response = TestAgent().run('Documento de teste')

        self.assertEqual(response.indice_risco, 12)
        mock_langfuse.assert_not_called()
        mock_agno.assert_not_called()
        mock_callback.assert_not_called()
        chain.invoke.assert_called_once_with({'documento': 'Documento de teste'}, config=None)

    @override_settings(LANGFUSE_ENABLED=True)
    def test_langfuse_client_recebe_mascara_otel(self):
        handler = object()
        chain = Mock()
        chain.invoke.return_value = self._response()

        class TestAgent(JurisprudenciaAI):
            def _build_chain(self):
                return chain

        tracer_provider = object()
        langfuse_client = Mock()
        langfuse_client._resources.tracer_provider = tracer_provider
        instrumentor = Mock()

        with patch('langfuse.Langfuse', return_value=langfuse_client) as mock_langfuse, \
             patch('openinference.instrumentation.agno.AgnoInstrumentor', return_value=instrumentor), \
             patch('langfuse.langchain.CallbackHandler', return_value=handler):
            TestAgent().run('Documento de teste')

        mock_langfuse.assert_called_once_with(mask_otel_spans=mask_otel_spans)
        instrumentor.instrument.assert_called_once_with(tracer_provider=tracer_provider)
        chain.invoke.assert_called_once_with(
            {'documento': 'Documento de teste'},
            config={'callbacks': [handler]},
        )

    @override_settings(LANGFUSE_ENABLED=True)
    def test_langfuse_export_falha_nao_quebra_analise(self):
        response = self._response()
        _FailingSpanExporter.export_calls = 0
        from langfuse import Langfuse as RealLangfuse

        class TestAgent(JurisprudenciaAI):
            def _build_chain(self):
                return RunnableLambda(lambda _: response)

        env = {
            'LANGFUSE_PUBLIC_KEY': 'pk-lf-test',
            'LANGFUSE_SECRET_KEY': 'sk-lf-test',
        }

        def build_langfuse_with_failing_exporter(**kwargs):
            return RealLangfuse(**kwargs, span_exporter=_FailingSpanExporter())

        with patch.dict(os.environ, env, clear=False), \
             patch('langfuse.Langfuse', side_effect=build_langfuse_with_failing_exporter), \
             patch('openinference.instrumentation.agno.AgnoInstrumentor'):
            started_at = time.monotonic()
            response = TestAgent().run('Documento jurídico sensível')
            elapsed = time.monotonic() - started_at

        self.assertEqual(response.indice_risco, 12)
        self.assertLess(elapsed, 5)
        self._shutdown_langfuse_clients()
        self.assertGreater(_FailingSpanExporter.export_calls, 0)

    @override_settings(LANGFUSE_ENABLED=True)
    def test_agno_streaming_span_fecha_apos_consumo_do_generator(self):
        exporter = _CollectingSpanExporter()
        captured = {}
        from langfuse import Langfuse as RealLangfuse

        env = {
            'LANGFUSE_PUBLIC_KEY': 'pk-lf-test',
            'LANGFUSE_SECRET_KEY': 'sk-lf-test',
        }

        def build_langfuse_with_collecting_exporter(**kwargs):
            client = RealLangfuse(**kwargs, span_exporter=exporter)
            captured['tracer_provider'] = client._resources.tracer_provider
            return client

        with patch.dict(os.environ, env, clear=False), \
             patch('langfuse.Langfuse', side_effect=build_langfuse_with_collecting_exporter):
            observability.ensure_agno_tracing()

            agent = Agent(model=_FakeStreamingModel(), name='Fake Agent')
            stream = agent.run('pergunta teste', stream=True, stream_events=True)
            first_event = next(stream)

            captured['tracer_provider'].force_flush()
            spans_before_stream_end = len(exporter.spans)

            remaining_events = list(stream)
            captured['tracer_provider'].force_flush()

        self.assertEqual(first_event.event, 'RunStarted')
        self.assertEqual(spans_before_stream_end, 0)
        self.assertTrue(any(getattr(event, 'content', None) == 'ultimo' for event in remaining_events))
        self.assertTrue(any(span.name == 'Fake_Agent.run' for span in exporter.spans))

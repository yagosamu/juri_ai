import os
import time
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
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
             patch('langfuse.langchain.CallbackHandler') as mock_callback:
            response = TestAgent().run('Documento de teste')

        self.assertEqual(response.indice_risco, 12)
        mock_langfuse.assert_not_called()
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

        with patch('langfuse.Langfuse') as mock_langfuse, \
             patch('langfuse.langchain.CallbackHandler', return_value=handler):
            TestAgent().run('Documento de teste')

        mock_langfuse.assert_called_once_with(mask_otel_spans=mask_otel_spans)
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
             patch('langfuse.Langfuse', side_effect=build_langfuse_with_failing_exporter):
            started_at = time.monotonic()
            response = TestAgent().run('Documento jurídico sensível')
            elapsed = time.monotonic() - started_at

        self.assertEqual(response.indice_risco, 12)
        self.assertLess(elapsed, 5)
        self._shutdown_langfuse_clients()
        self.assertGreater(_FailingSpanExporter.export_calls, 0)

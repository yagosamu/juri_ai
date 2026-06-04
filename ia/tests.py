from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from ia.tasks import atualizar_indices_economicos
from usuarios.models import Cliente, TemplateDocumento


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

from unittest.mock import patch

from django.test import TestCase

from ia.tasks import atualizar_indices_economicos


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

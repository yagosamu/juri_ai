from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import TestCase

from usuarios.models import IndiceEconomico
from usuarios.services.indices import (
    _calcular_taxa_legal,
    _janelas_consulta,
    importar_indices_bcb,
)


class ImportarIndicesCommandTests(TestCase):
    @patch('usuarios.services.indices.requests.get')
    def test_importa_indice_especifico_do_bcb(self, mock_get):
        response = Mock()
        response.json.return_value = [
            {'data': '01/01/2024', 'valor': '1.12'},
            {'data': '15/02/2024', 'valor': '0.83'},
        ]
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        out = StringIO()
        resultado = importar_indices_bcb(tipos=['selic'], ano_inicio=2024, output=out)

        mock_get.assert_called_once()
        url = mock_get.call_args.args[0]
        self.assertIn('bcdata.sgs.4390', url)
        self.assertIn('dataInicial=01/01/2024', url)
        self.assertEqual(
            mock_get.call_args.kwargs['headers'],
            {
                'Accept': 'application/json',
                'User-Agent': 'JuriAI/1.0',
            },
        )
        self.assertEqual(mock_get.call_args.kwargs['timeout'], 30)

        self.assertEqual(IndiceEconomico.objects.filter(tipo='selic').count(), 2)
        indice = IndiceEconomico.objects.get(tipo='selic', data=date(2024, 2, 1))
        self.assertEqual(indice.valor, Decimal('0.83'))
        self.assertEqual(indice.fonte, 'bcb')
        self.assertIn('SELIC: 2 criados, 0 atualizados', out.getvalue())
        self.assertEqual(resultado, {'selic': 2})

    def test_calcula_taxa_legal_a_partir_de_setembro_2024(self):
        IndiceEconomico.objects.create(
            tipo='selic',
            data=date(2024, 9, 1),
            valor=Decimal('0.90'),
            fonte='bcb',
        )
        IndiceEconomico.objects.create(
            tipo='ipca_e',
            data=date(2024, 9, 1),
            valor=Decimal('0.40'),
            fonte='bcb',
        )

        resumo = _calcular_taxa_legal(date(2024, 9, 1), date(2024, 9, 1))

        taxa = IndiceEconomico.objects.get(tipo='taxa_legal', data=date(2024, 9, 1))
        self.assertEqual(taxa.valor, Decimal('0.50'))
        self.assertEqual(taxa.fonte, 'bcb')
        self.assertEqual(resumo['criados'], 1)
        self.assertEqual(resumo['atualizados'], 0)

    def test_divide_serie_diaria_em_janelas_de_cinco_anos(self):
        janelas = _janelas_consulta(
            date(1994, 1, 1),
            date(2026, 5, 13),
            {'periodicidade': 'diaria'},
        )

        self.assertEqual(
            janelas,
            [
                (date(1994, 1, 1), date(1998, 12, 31)),
                (date(1999, 1, 1), date(2003, 12, 31)),
                (date(2004, 1, 1), date(2008, 12, 31)),
                (date(2009, 1, 1), date(2013, 12, 31)),
                (date(2014, 1, 1), date(2018, 12, 31)),
                (date(2019, 1, 1), date(2023, 12, 31)),
                (date(2024, 1, 1), date(2026, 5, 13)),
            ],
        )

    @patch('usuarios.management.commands.importar_indices.importar_indices_bcb')
    def test_command_chama_service_com_indice_especifico(self, mock_importar):
        mock_importar.return_value = {'tr': 1}

        out = StringIO()
        call_command('importar_indices', indice='tr', ano_inicio=2025, stdout=out)

        mock_importar.assert_called_once()
        self.assertEqual(mock_importar.call_args.kwargs['tipos'], ['tr'])
        self.assertEqual(mock_importar.call_args.kwargs['ano_inicio'], 2025)
        self.assertIn('Total de registros novos: 1', out.getvalue())

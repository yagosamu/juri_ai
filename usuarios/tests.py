from datetime import date
from decimal import Decimal
import json
from io import StringIO
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from usuarios.models import CalculoJudicial, Cliente, IndiceEconomico, Processo
from usuarios.services.calculo import calcular_debito
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


class CalculoDebitoTests(TestCase):
    def test_calcula_correcao_e_juros_simples_com_tabela_mensal(self):
        IndiceEconomico.objects.create(
            tipo='ipca_e',
            data=date(2024, 1, 1),
            valor=Decimal('1.00'),
            fonte='bcb',
        )
        IndiceEconomico.objects.create(
            tipo='ipca_e',
            data=date(2024, 2, 1),
            valor=Decimal('2.00'),
            fonte='bcb',
        )

        resultado = calcular_debito(
            valor_principal=Decimal('1000.00'),
            data_inicio=date(2024, 1, 1),
            data_fim=date(2024, 2, 29),
            indice_correcao='ipca_e',
            juros_tipo='simples_1',
        )

        self.assertEqual(resultado['valor_principal'], Decimal('1000.00'))
        self.assertEqual(resultado['valor_corrigido'], Decimal('1030.20'))
        self.assertEqual(resultado['correcao_acumulada_percent'], Decimal('3.020000'))
        self.assertEqual(resultado['juros_valor'], Decimal('20.60'))
        self.assertEqual(resultado['subtotal'], Decimal('1050.80'))
        self.assertEqual(resultado['total'], Decimal('1050.80'))
        self.assertEqual(resultado['meses'], 2)
        self.assertEqual(len(resultado['tabela_mensal']), 2)
        self.assertEqual(resultado['tabela_mensal'][0]['mes'], '01/2024')
        self.assertEqual(resultado['tabela_mensal'][1]['subtotal'], Decimal('1050.80'))

    def test_meses_sem_indice_usam_zero_por_cento(self):
        IndiceEconomico.objects.create(
            tipo='ipca_e',
            data=date(2024, 1, 1),
            valor=Decimal('1.00'),
            fonte='bcb',
        )

        resultado = calcular_debito(
            valor_principal=Decimal('1000.00'),
            data_inicio=date(2024, 1, 1),
            data_fim=date(2024, 2, 29),
            indice_correcao='ipca_e',
            juros_tipo='customizado',
            juros_percentual=Decimal('0.00'),
        )

        self.assertEqual(resultado['valor_corrigido'], Decimal('1010.00'))
        self.assertEqual(resultado['tabela_mensal'][1]['indice_mensal'], Decimal('0.000000'))
        self.assertEqual(resultado['tabela_mensal'][1]['valor_corrigido'], Decimal('1010.00'))

    def test_selic_integral_nao_soma_juros_duas_vezes_no_subtotal(self):
        IndiceEconomico.objects.create(
            tipo='selic',
            data=date(2024, 1, 1),
            valor=Decimal('1.00'),
            fonte='bcb',
        )

        resultado = calcular_debito(
            valor_principal=Decimal('1000.00'),
            data_inicio=date(2024, 1, 1),
            data_fim=date(2024, 1, 31),
            indice_correcao='ipca_e',
            juros_tipo='selic',
        )

        self.assertEqual(resultado['valor_corrigido'], Decimal('1010.00'))
        self.assertEqual(resultado['juros_valor'], Decimal('10.00'))
        self.assertEqual(resultado['subtotal'], Decimal('1010.00'))
        self.assertEqual(resultado['total'], Decimal('1010.00'))

    def test_taxa_legal_aplica_juros_compostos_sobre_valor_corrigido(self):
        IndiceEconomico.objects.create(
            tipo='ipca_e',
            data=date(2024, 9, 1),
            valor=Decimal('1.00'),
            fonte='bcb',
        )
        IndiceEconomico.objects.create(
            tipo='taxa_legal',
            data=date(2024, 9, 1),
            valor=Decimal('2.00'),
            fonte='bcb',
        )

        resultado = calcular_debito(
            valor_principal=Decimal('1000.00'),
            data_inicio=date(2024, 9, 1),
            data_fim=date(2024, 9, 30),
            indice_correcao='ipca_e',
            juros_tipo='taxa_legal',
        )

        self.assertEqual(resultado['valor_corrigido'], Decimal('1010.00'))
        self.assertEqual(resultado['juros_valor'], Decimal('20.20'))
        self.assertEqual(resultado['subtotal'], Decimal('1030.20'))

    def test_valida_periodo_e_valor_principal(self):
        with self.assertRaisesMessage(ValueError, 'valor principal'):
            calcular_debito(
                Decimal('0.00'),
                date(2024, 1, 1),
                date(2024, 1, 31),
                'ipca_e',
                'simples_1',
            )

        with self.assertRaisesMessage(ValueError, 'data inicial'):
            calcular_debito(
                Decimal('1000.00'),
                date(2024, 2, 1),
                date(2024, 1, 31),
                'ipca_e',
                'simples_1',
            )


class CalculadoraViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='advogado', password='abc123')
        self.outro_user = User.objects.create_user(username='outro', password='abc123')
        self.cliente = Cliente.objects.create(
            nome='Cliente Teste',
            email='cliente@example.com',
            tipo='PF',
            user=self.user,
        )
        self.processo = Processo.objects.create(
            numero_cnj='12345678920248260001',
            tribunal='tjsp',
            tipo_acao='Cível',
            valor_causa=Decimal('10000.00'),
            data_distribuicao=date(2024, 1, 10),
            cliente=self.cliente,
            user=self.user,
        )
        self.client.force_login(self.user)

    def test_urls_da_calculadora_resolvem(self):
        self.assertEqual(reverse('calculadora'), '/usuarios/calculadora/')
        self.assertEqual(reverse('salvar_calculo'), '/usuarios/calculadora/salvar/')
        self.assertEqual(reverse('lista_calculos'), '/usuarios/calculadora/historico/')

    def test_calculadora_get_preenche_processo_da_querystring(self):
        response = self.client.get(reverse('calculadora'), {'processo_id': self.processo.id})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="10.000,00"')
        self.assertContains(response, 'value="10/01/2024"')

    def test_calculadora_post_retorna_resultado_json(self):
        IndiceEconomico.objects.create(
            tipo='ipca_e',
            data=date(2024, 1, 1),
            valor=Decimal('1.00'),
            fonte='bcb',
        )
        payload = {
            'valor_principal': '1.000,00',
            'data_inicio': '01/01/2024',
            'data_fim': '31/01/2024',
            'indice_correcao': 'ipca_e',
            'juros_tipo': 'simples_1',
            'juros_percentual': '1,00',
            'multa_523': False,
            'honorarios_sucumb': False,
            'honorarios_percent': '10,00',
            'processo_id': self.processo.id,
        }

        response = self.client.post(
            reverse('calculadora'),
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['resultado']['valor_corrigido'], 1010.0)
        self.assertEqual(data['resultado']['tabela_mensal'][0]['mes'], '01/2024')

    def test_salvar_calculo_cria_registro_do_usuario(self):
        payload = {
            'processo_id': self.processo.id,
            'valor_principal': '1.000,00',
            'data_inicio': '01/01/2024',
            'data_fim': '31/01/2024',
            'indice_correcao': 'ipca_e',
            'juros_tipo': 'simples_1',
            'juros_percentual': '1,00',
            'multa_523': True,
            'honorarios_sucumb': True,
            'honorarios_percent': '10,00',
            'resultado_json': {'total': 1122.0, 'tabela_mensal': []},
        }

        response = self.client.post(
            reverse('salvar_calculo'),
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        calculo = CalculoJudicial.objects.get(id=data['id'])
        self.assertEqual(calculo.user, self.user)
        self.assertEqual(calculo.processo, self.processo)
        self.assertEqual(calculo.resultado_json['total'], 1122.0)

    def test_lista_calculos_filtra_por_usuario(self):
        CalculoJudicial.objects.create(
            valor_principal=Decimal('1000.00'),
            data_inicio=date(2024, 1, 1),
            data_fim=date(2024, 1, 31),
            user=self.user,
        )
        CalculoJudicial.objects.create(
            valor_principal=Decimal('2000.00'),
            data_inicio=date(2024, 1, 1),
            data_fim=date(2024, 1, 31),
            user=self.outro_user,
        )

        response = self.client.get(reverse('lista_calculos'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'R$ 1.000,00')
        self.assertNotContains(response, 'R$ 2.000,00')

    def test_exportar_calculo_requer_ownership_e_retorna_pdf(self):
        calculo = CalculoJudicial.objects.create(
            processo=self.processo,
            valor_principal=Decimal('1000.00'),
            data_inicio=date(2024, 1, 1),
            data_fim=date(2024, 1, 31),
            resultado_json={
                'valor_corrigido': 1010.0,
                'juros_valor': 10.1,
                'multa_valor': 0.0,
                'honorarios_valor': 0.0,
                'total': 1020.1,
                'tabela_mensal': [
                    {
                        'mes': '01/2024',
                        'indice_mensal': 1.0,
                        'correcao_acumulada': 1.01,
                        'valor_corrigido': 1010.0,
                        'juros_acumulado': 10.1,
                        'subtotal': 1020.1,
                    }
                ],
            },
            user=self.user,
        )

        response = self.client.post(reverse('exportar_calculo', kwargs={'id': calculo.id}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

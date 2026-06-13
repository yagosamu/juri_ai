from datetime import date
from decimal import Decimal
import json
from io import StringIO
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from usuarios.models import CalculoJudicial, Cliente, IndiceEconomico, LinkProcesso, Processo
from usuarios.services.calculo import (
    calcular_debito,
    calcular_debito_multiplo,
    calcular_debito_tabela_tj,
    comparar_cenarios,
)
from usuarios.services.indices import (
    _calcular_taxa_legal,
    _janelas_consulta,
    importar_indices_bcb,
)
from usuarios.services.calculo_trabalhista import calcular_verbas_trabalhistas
from usuarios.services.tabelas_tj import listar_tribunais_disponiveis, obter_indice_por_periodo


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
    def test_calcula_verbas_trabalhistas_sem_justa_causa(self):
        resultado = calcular_verbas_trabalhistas(
            salario_base=Decimal('5000.00'),
            data_admissao=date(2020, 3, 1),
            data_demissao=date(2024, 11, 15),
            tipo_demissao='sem_justa_causa',
            horas_extras_50=30,
            horas_extras_100=8,
            aviso_previo='indenizado',
        )

        verbas = {verba['nome']: verba for verba in resultado['verbas']}
        deducoes = {deducao['nome']: deducao for deducao in resultado['deducoes']}

        self.assertEqual(resultado['dados_entrada']['meses_trabalhados'], 57)
        self.assertEqual(verbas['Saldo de salário']['valor'], Decimal('2500.00'))
        self.assertEqual(verbas['13º proporcional']['avos'], 11)
        self.assertEqual(verbas['13º proporcional']['valor'], Decimal('4583.33'))
        self.assertEqual(verbas['Férias proporcionais']['avos'], 9)
        self.assertEqual(verbas['Férias proporcionais']['valor'], Decimal('3750.00'))
        self.assertEqual(verbas['1/3 constitucional']['valor'], Decimal('1250.00'))
        self.assertEqual(verbas['Aviso prévio indenizado']['dias'], 42)
        self.assertEqual(verbas['Aviso prévio indenizado']['valor'], Decimal('7000.00'))
        self.assertEqual(verbas['Horas extras 50%']['valor'], Decimal('1022.73'))
        self.assertEqual(verbas['Horas extras 100%']['valor'], Decimal('363.64'))
        self.assertEqual(verbas['DSR sobre horas extras']['valor'], Decimal('231.06'))
        self.assertEqual(verbas['Multa 40% FGTS']['valor'], Decimal('9120.00'))
        self.assertEqual(resultado['total_bruto'], Decimal('29820.76'))
        self.assertIn('INSS (estimativa)', deducoes)
        self.assertIn('IRRF (estimativa)', deducoes)
        self.assertLess(resultado['total_liquido'], resultado['total_bruto'])

    def test_justa_causa_nao_calcula_aviso_multa_e_decimo(self):
        resultado = calcular_verbas_trabalhistas(
            salario_base=Decimal('3000.00'),
            data_admissao=date(2024, 1, 1),
            data_demissao=date(2024, 6, 10),
            tipo_demissao='com_justa_causa',
        )

        nomes = [verba['nome'] for verba in resultado['verbas']]
        self.assertIn('Saldo de salário', nomes)
        self.assertNotIn('13º proporcional', nomes)
        self.assertNotIn('Aviso prévio indenizado', nomes)
        self.assertNotIn('Multa 40% FGTS', nomes)

    def test_obtem_indice_por_periodo_do_tjsp_e_fallback(self):
        self.assertEqual(obter_indice_por_periodo('tjsp', date(2004, 1, 1)), 'igpm')
        self.assertEqual(obter_indice_por_periodo('tjsp', date(2006, 4, 1)), 'ipca_e')
        self.assertEqual(obter_indice_por_periodo('nao_existe', date(2024, 1, 1)), 'ipca_e')

        tribunais = listar_tribunais_disponiveis()
        self.assertIn({'codigo': 'tjsp', 'nome': 'Tabela Prática TJSP'}, tribunais)

    def test_calcula_debito_com_tabela_tj_e_periodos_aplicados(self):
        IndiceEconomico.objects.create(
            tipo='igpm',
            data=date(2006, 3, 1),
            valor=Decimal('1.00'),
            fonte='bcb',
        )
        IndiceEconomico.objects.create(
            tipo='ipca_e',
            data=date(2006, 4, 1),
            valor=Decimal('2.00'),
            fonte='bcb',
        )

        resultado = calcular_debito_tabela_tj(
            valor_principal=Decimal('1000.00'),
            data_inicio=date(2006, 3, 1),
            data_fim=date(2006, 4, 30),
            tribunal='tjsp',
            juros_tipo='simples_1',
        )

        self.assertEqual(resultado['tribunal'], 'tjsp')
        self.assertEqual(resultado['tribunal_nome'], 'Tabela Prática TJSP')
        self.assertEqual(resultado['valor_corrigido'], Decimal('1030.20'))
        self.assertEqual(resultado['juros_valor'], Decimal('20.60'))
        self.assertEqual(resultado['total'], Decimal('1050.80'))
        self.assertEqual(len(resultado['periodos_aplicados']), 2)
        self.assertEqual(resultado['periodos_aplicados'][0]['inicio'], date(2006, 3, 1))
        self.assertEqual(resultado['periodos_aplicados'][0]['fim'], date(2006, 3, 1))
        self.assertEqual(resultado['periodos_aplicados'][0]['indice'], 'igpm')
        self.assertEqual(resultado['periodos_aplicados'][0]['meses'], 1)
        self.assertEqual(resultado['periodos_aplicados'][1]['inicio'], date(2006, 4, 1))
        self.assertEqual(resultado['periodos_aplicados'][1]['indice'], 'ipca_e')
        self.assertEqual(resultado['tabela_mensal'][0]['indice_tipo'], 'igpm')
        self.assertEqual(resultado['tabela_mensal'][1]['indice_tipo'], 'ipca_e')

    def test_compara_cenarios_com_maior_menor_e_diferenca(self):
        resultado = comparar_cenarios(
            valor_principal=Decimal('1000.00'),
            data_inicio=date(2024, 1, 1),
            data_fim=date(2024, 2, 29),
            cenarios=[
                {
                    'nome': 'IPCA-E + 1%',
                    'indice_correcao': 'ipca_e',
                    'juros_tipo': 'simples_1',
                    'juros_percentual': Decimal('1.00'),
                },
                {
                    'nome': 'INPC + 0,5%',
                    'indice_correcao': 'inpc',
                    'juros_tipo': 'simples_05',
                    'juros_percentual': Decimal('0.50'),
                },
            ],
        )

        self.assertEqual(len(resultado['cenarios']), 2)
        self.assertEqual(resultado['cenarios'][0]['nome'], 'IPCA-E + 1%')
        self.assertEqual(resultado['cenarios'][0]['resultado']['total'], Decimal('1020.00'))
        self.assertEqual(resultado['cenarios'][1]['resultado']['total'], Decimal('1010.00'))
        self.assertEqual(resultado['comparativo']['maior_total']['nome'], 'IPCA-E + 1%')
        self.assertEqual(resultado['comparativo']['maior_total']['valor'], Decimal('1020.00'))
        self.assertEqual(resultado['comparativo']['menor_total']['nome'], 'INPC + 0,5%')
        self.assertEqual(resultado['comparativo']['menor_total']['valor'], Decimal('1010.00'))
        self.assertEqual(resultado['comparativo']['diferenca'], Decimal('10.00'))
        self.assertEqual(resultado['comparativo']['diferenca_percent'], Decimal('0.990099'))

    def test_comparacao_exige_dois_ou_tres_cenarios(self):
        with self.assertRaisesMessage(ValueError, '2 a 3 cenários'):
            comparar_cenarios(
                valor_principal=Decimal('1000.00'),
                data_inicio=date(2024, 1, 1),
                data_fim=date(2024, 1, 31),
                cenarios=[
                    {
                        'nome': 'Único',
                        'indice_correcao': 'ipca_e',
                        'juros_tipo': 'simples_1',
                        'juros_percentual': Decimal('1.00'),
                    },
                ],
            )

    def test_calcula_debito_multiplo_consolida_parcelas(self):
        resultado = calcular_debito_multiplo(
            parcelas=[
                {'valor': Decimal('100.00'), 'data': date(2024, 1, 1), 'descricao': 'Aluguel jan'},
                {'valor': Decimal('200.00'), 'data': date(2024, 3, 1), 'descricao': 'Aluguel mar'},
            ],
            data_fim=date(2024, 3, 31),
            indice_correcao='ipca_e',
            juros_tipo='simples_1',
            multa_523=True,
            honorarios_sucumb=True,
            honorarios_percent=Decimal('10.00'),
        )

        self.assertEqual(len(resultado['parcelas']), 2)
        self.assertEqual(resultado['parcelas'][0]['descricao'], 'Aluguel jan')
        self.assertEqual(resultado['parcelas'][0]['valor_principal'], Decimal('100.00'))
        self.assertEqual(resultado['parcelas'][0]['data_inicio'], date(2024, 1, 1))
        self.assertEqual(resultado['consolidado']['valor_principal_total'], Decimal('300.00'))
        self.assertEqual(resultado['consolidado']['valor_corrigido_total'], Decimal('300.00'))
        self.assertEqual(resultado['consolidado']['juros_total'], Decimal('5.00'))
        self.assertEqual(resultado['consolidado']['subtotal'], Decimal('305.00'))
        self.assertEqual(resultado['consolidado']['multa_valor'], Decimal('30.50'))
        self.assertEqual(resultado['consolidado']['honorarios_valor'], Decimal('33.55'))
        self.assertEqual(resultado['consolidado']['total'], Decimal('369.05'))

    def test_calculo_multiplo_exige_parcelas(self):
        with self.assertRaisesMessage(ValueError, 'parcela'):
            calcular_debito_multiplo(
                parcelas=[],
                data_fim=date(2024, 3, 31),
                indice_correcao='ipca_e',
                juros_tipo='simples_1',
            )

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
        self.assertContains(response, 'Comparar cenários')
        self.assertContains(response, 'Calculadora Trabalhista')
        self.assertContains(response, 'Tabela Prática TJSP')
        self.assertContains(response, 'value="tjsp" selected')

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

    def test_calculadora_post_usa_tabela_tj(self):
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
            'tribunal': 'tjsp',
            'indice_correcao': 'igpm',
            'juros_tipo': 'simples_1',
            'juros_percentual': '1,00',
            'multa_523': False,
            'honorarios_sucumb': False,
            'honorarios_percent': '10,00',
        }

        response = self.client.post(
            reverse('calculadora'),
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['resultado']['tribunal'], 'tjsp')
        self.assertEqual(data['resultado']['tribunal_nome'], 'Tabela Prática TJSP')
        self.assertEqual(data['resultado']['periodos_aplicados'][0]['indice'], 'ipca_e')
        self.assertEqual(data['resultado']['valor_corrigido'], 1010.0)

    def test_calculadora_post_calcula_verbas_trabalhistas(self):
        payload = {
            'trabalhista': True,
            'salario_base': '5.000,00',
            'data_admissao': '01/03/2020',
            'data_demissao': '15/11/2024',
            'tipo_demissao': 'sem_justa_causa',
            'horas_extras_50': 30,
            'horas_extras_100': 8,
            'aviso_previo': 'indenizado',
            'saldo_fgts': '',
        }

        response = self.client.post(
            reverse('calculadora'),
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['resultado']['total_bruto'], 29820.76)
        self.assertEqual(data['resultado']['verbas'][0]['nome'], 'Saldo de salário')
        self.assertIn('deducoes', data['resultado'])

    def test_calculadora_post_aceita_multiplas_parcelas(self):
        payload = {
            'data_fim': '31/03/2024',
            'indice_correcao': 'ipca_e',
            'juros_tipo': 'simples_1',
            'juros_percentual': '1,00',
            'multa_523': False,
            'honorarios_sucumb': False,
            'honorarios_percent': '10,00',
            'parcelas': [
                {'descricao': 'Parcela 1', 'valor': '100,00', 'data': '01/01/2024'},
                {'descricao': 'Parcela 2', 'valor': '200,00', 'data': '01/03/2024'},
            ],
        }

        response = self.client.post(
            reverse('calculadora'),
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(len(data['resultado']['parcelas']), 2)
        self.assertEqual(data['resultado']['consolidado']['valor_principal_total'], 300.0)
        self.assertEqual(data['resultado']['consolidado']['total'], 305.0)

    def test_calculadora_post_compara_cenarios(self):
        payload = {
            'comparar': True,
            'valor_principal': '1.000,00',
            'data_inicio': '01/01/2024',
            'data_fim': '29/02/2024',
            'multa_523': False,
            'honorarios_sucumb': False,
            'honorarios_percent': '10,00',
            'cenarios': [
                {
                    'nome': 'IPCA-E + 1%',
                    'indice_correcao': 'ipca_e',
                    'juros_tipo': 'simples_1',
                    'juros_percentual': '1,00',
                },
                {
                    'nome': 'INPC + 0,5%',
                    'indice_correcao': 'inpc',
                    'juros_tipo': 'simples_05',
                    'juros_percentual': '0,50',
                },
            ],
        }

        response = self.client.post(
            reverse('calculadora'),
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(len(data['resultado']['cenarios']), 2)
        self.assertEqual(data['resultado']['comparativo']['maior_total']['nome'], 'IPCA-E + 1%')
        self.assertEqual(data['resultado']['comparativo']['diferenca'], 10.0)

    def test_salvar_calculo_multiplo_grava_soma_e_menor_data(self):
        payload = {
            'data_fim': '31/03/2024',
            'indice_correcao': 'ipca_e',
            'juros_tipo': 'simples_1',
            'juros_percentual': '1,00',
            'multa_523': False,
            'honorarios_sucumb': False,
            'honorarios_percent': '10,00',
            'parcelas': [
                {'descricao': 'Parcela 1', 'valor': '100,00', 'data': '01/01/2024'},
                {'descricao': 'Parcela 2', 'valor': '200,00', 'data': '01/03/2024'},
            ],
            'resultado_json': {
                'parcelas': [
                    {'descricao': 'Parcela 1', 'valor_principal': 100.0, 'data_inicio': '01/01/2024'},
                    {'descricao': 'Parcela 2', 'valor_principal': 200.0, 'data_inicio': '01/03/2024'},
                ],
                'consolidado': {'total': 305.0},
            },
        }

        response = self.client.post(
            reverse('salvar_calculo'),
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        calculo = CalculoJudicial.objects.get(id=response.json()['id'])
        self.assertEqual(calculo.valor_principal, Decimal('300.00'))
        self.assertEqual(calculo.data_inicio, date(2024, 1, 1))
        self.assertEqual(calculo.resultado_json['consolidado']['total'], 305.0)

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

    def test_salvar_calculo_persiste_marco_inicial_juridico(self):
        payload = {
            'processo_id': self.processo.id,
            'valor_principal': '1.000,00',
            'marco_inicial_tipo': 'publicacao',
            'marco_inicial_observacao': 'Conforme certidão de publicação de 14/03/2025.',
            'data_inicio': '14/03/2025',
            'data_fim': '14/04/2025',
            'indice_correcao': 'ipca_e',
            'juros_tipo': 'simples_1',
            'juros_percentual': '1,00',
            'multa_523': False,
            'honorarios_sucumb': False,
            'honorarios_percent': '10,00',
            'resultado_json': {'total': 1010.0, 'tabela_mensal': []},
        }

        response = self.client.post(
            reverse('salvar_calculo'),
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        calculo = CalculoJudicial.objects.get(id=response.json()['id'])
        self.assertEqual(calculo.marco_inicial_tipo, 'publicacao')
        self.assertEqual(calculo.marco_inicial_observacao, 'Conforme certidão de publicação de 14/03/2025.')
        self.assertEqual(calculo.data_inicio, date(2025, 3, 14))

    def test_salvar_calculo_persiste_juros_customizado_e_honorarios_percentuais(self):
        payload = {
            'processo_id': self.processo.id,
            'valor_principal': '2.000,00',
            'marco_inicial_tipo': 'citacao',
            'data_inicio': '10/02/2025',
            'data_fim': '10/04/2025',
            'indice_correcao': 'ipca_e',
            'juros_tipo': 'customizado',
            'juros_percentual': '2,35',
            'multa_523': True,
            'honorarios_sucumb': True,
            'honorarios_percent': '15,00',
            'resultado_json': {'total': 2500.0, 'tabela_mensal': []},
        }

        response = self.client.post(
            reverse('salvar_calculo'),
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        calculo = CalculoJudicial.objects.get(id=response.json()['id'])
        self.assertEqual(calculo.marco_inicial_tipo, 'citacao')
        self.assertEqual(calculo.juros_tipo, 'customizado')
        self.assertEqual(calculo.juros_percentual, Decimal('2.35'))
        self.assertTrue(calculo.honorarios_sucumb)
        self.assertEqual(calculo.honorarios_percent, Decimal('15.00'))

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

    def test_lista_calculos_exibe_parametros_juridicos_do_calculo(self):
        CalculoJudicial.objects.create(
            valor_principal=Decimal('1000.00'),
            marco_inicial_tipo='publicacao',
            marco_inicial_observacao='Conforme certidão de publicação.',
            data_inicio=date(2025, 3, 14),
            data_fim=date(2025, 4, 14),
            juros_tipo='customizado',
            juros_percentual=Decimal('2.35'),
            honorarios_sucumb=True,
            honorarios_percent=Decimal('15.00'),
            user=self.user,
        )

        response = self.client.get(reverse('lista_calculos'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Publicação/certificação')
        self.assertContains(response, 'Conforme certidão de publicação.')
        self.assertContains(response, 'Percentual customizado')
        self.assertContains(response, '2,35% a.m.')
        self.assertContains(response, 'Honorários 15,00%')

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

    def test_exportar_calculo_multiplo_retorna_pdf(self):
        calculo = CalculoJudicial.objects.create(
            processo=self.processo,
            valor_principal=Decimal('300.00'),
            data_inicio=date(2024, 1, 1),
            data_fim=date(2024, 3, 31),
            resultado_json={
                'parcelas': [
                    {
                        'descricao': 'Parcela 1',
                        'valor_principal': 100.0,
                        'data_inicio': '01/01/2024',
                        'valor_corrigido': 100.0,
                        'juros_valor': 3.0,
                        'subtotal': 103.0,
                    },
                    {
                        'descricao': 'Parcela 2',
                        'valor_principal': 200.0,
                        'data_inicio': '01/03/2024',
                        'valor_corrigido': 200.0,
                        'juros_valor': 2.0,
                        'subtotal': 202.0,
                    },
                ],
                'consolidado': {
                    'valor_principal_total': 300.0,
                    'valor_corrigido_total': 300.0,
                    'juros_total': 5.0,
                    'subtotal': 305.0,
                    'multa_valor': 0.0,
                    'honorarios_valor': 0.0,
                    'total': 305.0,
                },
            },
            user=self.user,
        )

        response = self.client.post(reverse('exportar_calculo', kwargs={'id': calculo.id}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_exportar_calculo_tabela_tj_retorna_pdf(self):
        calculo = CalculoJudicial.objects.create(
            processo=self.processo,
            valor_principal=Decimal('1000.00'),
            data_inicio=date(2006, 3, 1),
            data_fim=date(2006, 4, 30),
            resultado_json={
                'tribunal': 'tjsp',
                'tribunal_nome': 'Tabela Prática TJSP',
                'valor_corrigido': 1030.20,
                'juros_valor': 20.60,
                'multa_valor': 0.0,
                'honorarios_valor': 0.0,
                'total': 1050.80,
                'periodos_aplicados': [
                    {'inicio': '01/03/2006', 'fim': '01/03/2006', 'indice': 'igpm', 'meses': 1},
                    {'inicio': '01/04/2006', 'fim': '01/04/2006', 'indice': 'ipca_e', 'meses': 1},
                ],
                'tabela_mensal': [],
            },
            user=self.user,
        )

        response = self.client.post(reverse('exportar_calculo', kwargs={'id': calculo.id}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))


class LinksProcessoViewsTests(TestCase):
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
            cliente=self.cliente,
            user=self.user,
        )
        self.client.force_login(self.user)

    def test_cria_link_externo_do_processo(self):
        response = self.client.post(
            reverse('criar_link_processo', args=[self.processo.id]),
            {
                'titulo': 'e-SAJ TJSP',
                'url': 'https://eproc-consulta.tjsp.jus.br/consulta_1g/externo_controlador.php',
                'observacao': 'Consulta pública de primeiro grau',
            },
        )

        self.assertRedirects(response, reverse('processo', args=[self.processo.id]) + '?tab=links')
        link = LinkProcesso.objects.get(processo=self.processo)
        self.assertEqual(link.user, self.user)
        self.assertEqual(link.titulo, 'e-SAJ TJSP')
        self.assertEqual(link.observacao, 'Consulta pública de primeiro grau')

    def test_rejeita_url_sem_http_ou_https(self):
        response = self.client.post(
            reverse('criar_link_processo', args=[self.processo.id]),
            {
                'titulo': 'Consulta',
                'url': 'www.tjsp.jus.br',
            },
        )

        self.assertRedirects(response, reverse('processo', args=[self.processo.id]) + '?tab=links')
        self.assertFalse(LinkProcesso.objects.exists())

    def test_nao_exclui_link_de_outro_usuario(self):
        outro_cliente = Cliente.objects.create(
            nome='Outro Cliente',
            email='outro@example.com',
            tipo='PF',
            user=self.outro_user,
        )
        outro_processo = Processo.objects.create(
            numero_cnj='22345678920248260001',
            tribunal='tjsp',
            cliente=outro_cliente,
            user=self.outro_user,
        )
        link = LinkProcesso.objects.create(
            processo=outro_processo,
            user=self.outro_user,
            titulo='eproc',
            url='https://eproc.example.com',
        )

        response = self.client.post(reverse('excluir_link_processo', args=[link.id]))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(LinkProcesso.objects.filter(id=link.id).exists())

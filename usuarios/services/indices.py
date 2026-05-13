import time
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import requests
from django.utils import timezone

from usuarios.models import IndiceEconomico


SERIES_BCB = {
    'ipca_e': {'nome': 'IPCA-E', 'serie': 10764},
    'inpc': {'nome': 'INPC', 'serie': 188},
    'selic': {'nome': 'SELIC', 'serie': 4390},
    'tr': {'nome': 'TR', 'serie': 226, 'periodicidade': 'diaria'},
    'igpm': {'nome': 'IGP-M', 'serie': 189},
}


class ImportacaoIndicesError(Exception):
    pass


def importar_indices_bcb(tipos=None, ano_inicio=None, output=None):
    """
    Importa índices do BCB. Reutilizável pelo command e pela task.

    Args:
        tipos: lista de tipos para importar (None = todos)
        ano_inicio: ano inicial (None = 1994)

    Returns:
        dict com contadores por índice: {'selic': 12, 'ipca_e': 12, ...}
    """
    ano = ano_inicio or 1994
    if ano < 1994:
        raise ImportacaoIndicesError('O ano inicial minimo suportado e 1994.')

    tipos_importacao = list(tipos) if tipos else list(SERIES_BCB.keys())
    tipos_invalidos = [tipo for tipo in tipos_importacao if tipo not in SERIES_BCB]
    if tipos_invalidos:
        raise ImportacaoIndicesError(f'Indice invalido: {", ".join(tipos_invalidos)}')

    data_inicial = date(ano, 1, 1)
    data_final = timezone.now().date()

    resultado = {}
    for tipo in tipos_importacao:
        resumo = _importar_serie(tipo, data_inicial, data_final, output=output)
        resultado[tipo] = resumo['criados']
        _mostrar_resumo(tipo, resumo, output=output)

    if tipos is None:
        resumo = _calcular_taxa_legal(
            max(data_inicial, date(2024, 9, 1)),
            data_final,
            output=output,
        )
        resultado['taxa_legal'] = resumo['criados']
        _mostrar_resumo('taxa_legal', resumo, output=output)

    return resultado


def _write(output, mensagem):
    if output:
        output.write(mensagem)


def _importar_serie(tipo, data_inicial, data_final, output=None):
    config = SERIES_BCB[tipo]
    dados = []

    for inicio, fim in _janelas_consulta(data_inicial, data_final, config):
        dados.extend(_buscar_bcb(config, inicio, fim, output=output))

    return _salvar_registros(tipo, dados, fonte='bcb')


def _janelas_consulta(data_inicial, data_final, config):
    if config.get('periodicidade') != 'diaria':
        return [(data_inicial, data_final)]

    janelas = []
    inicio = data_inicial
    while inicio <= data_final:
        fim = min(date(inicio.year + 4, 12, 31), data_final)
        janelas.append((inicio, fim))
        inicio = date(fim.year + 1, 1, 1)
    return janelas


def _buscar_bcb(config, data_inicial, data_final, output=None):
    url = (
        f'https://api.bcb.gov.br/dados/serie/bcdata.sgs.{config["serie"]}/dados'
        f'?formato=json&dataInicial={data_inicial:%d/%m/%Y}'
        f'&dataFinal={data_final:%d/%m/%Y}'
    )
    _write(
        output,
        f'Importando {config["nome"]} ({data_inicial:%d/%m/%Y} a {data_final:%d/%m/%Y})...',
    )

    headers = {
        'Accept': 'application/json',
        'User-Agent': 'JuriAI/1.0',
    }
    try:
        return _get_json_bcb(url, headers, config, output=output)
    except requests.RequestException as exc:
        raise ImportacaoIndicesError(f'Erro ao buscar {config["nome"]} no BCB: {exc}') from exc
    except ValueError as exc:
        raise ImportacaoIndicesError(f'Resposta JSON invalida para {config["nome"]}.') from exc


def _get_json_bcb(url, headers, config, output=None):
    ultimo_erro = None
    for tentativa in range(1, 4):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            ultimo_erro = exc
            if tentativa == 3:
                raise
            _write(output, f'Tentativa {tentativa} falhou para {config["nome"]}; tentando novamente...')
            time.sleep(2)
    raise ultimo_erro


def _salvar_registros(tipo, dados, fonte):
    criados = 0
    atualizados = 0
    datas = []

    for item in dados:
        try:
            data_ref = datetime.strptime(item['data'], '%d/%m/%Y').date().replace(day=1)
            valor = Decimal(str(item['valor']).replace(',', '.'))
        except (KeyError, ValueError, InvalidOperation) as exc:
            raise ImportacaoIndicesError(f'Registro invalido para {tipo}: {item}') from exc

        _, criado = IndiceEconomico.objects.update_or_create(
            tipo=tipo,
            data=data_ref,
            defaults={'valor': valor, 'fonte': fonte},
        )
        criados += int(criado)
        atualizados += int(not criado)
        datas.append(data_ref)

    return {
        'criados': criados,
        'atualizados': atualizados,
        'data_min': min(datas) if datas else None,
        'data_max': max(datas) if datas else None,
    }


def _calcular_taxa_legal(data_inicial, data_final, output=None):
    _write(output, 'Calculando Taxa Legal...')
    criados = 0
    atualizados = 0
    datas = []

    selic_por_data = {
        indice.data: indice.valor
        for indice in IndiceEconomico.objects.filter(
            tipo='selic',
            data__gte=data_inicial,
            data__lte=data_final,
        )
    }
    ipca_e_por_data = {
        indice.data: indice.valor
        for indice in IndiceEconomico.objects.filter(
            tipo='ipca_e',
            data__gte=data_inicial,
            data__lte=data_final,
        )
    }

    for data_ref in sorted(selic_por_data.keys() & ipca_e_por_data.keys()):
        valor = selic_por_data[data_ref] - ipca_e_por_data[data_ref]
        _, criado = IndiceEconomico.objects.update_or_create(
            tipo='taxa_legal',
            data=data_ref,
            defaults={'valor': valor, 'fonte': 'bcb'},
        )
        criados += int(criado)
        atualizados += int(not criado)
        datas.append(data_ref)

    return {
        'criados': criados,
        'atualizados': atualizados,
        'data_min': min(datas) if datas else None,
        'data_max': max(datas) if datas else None,
    }


def _mostrar_resumo(tipo, resumo, output=None):
    nome = dict(IndiceEconomico.TIPO_CHOICES).get(tipo, tipo)
    if resumo['data_min'] and resumo['data_max']:
        periodo = f'{resumo["data_min"]:%m/%Y} -> {resumo["data_max"]:%m/%Y}'
    else:
        periodo = 'sem registros'

    _write(
        output,
        f'{nome}: {resumo["criados"]} criados, '
        f'{resumo["atualizados"]} atualizados | periodo: {periodo}',
    )

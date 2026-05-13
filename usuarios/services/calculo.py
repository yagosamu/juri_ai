from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from usuarios.models import IndiceEconomico


MOEDA = Decimal('0.01')
PERCENTUAL = Decimal('0.000001')
FATOR = Decimal('0.000001')
ZERO = Decimal('0')
UM = Decimal('1')
CEM = Decimal('100')


def calcular_debito(
    valor_principal: Decimal,
    data_inicio: date,
    data_fim: date,
    indice_correcao: str,
    juros_tipo: str,
    juros_percentual: Decimal = Decimal('1.00'),
    multa_523: bool = False,
    honorarios_sucumb: bool = False,
    honorarios_percent: Decimal = Decimal('10.00'),
) -> dict:
    """
    Calcula débito judicial com correção monetária e juros.
    """
    valor_principal = Decimal(valor_principal)
    juros_percentual = Decimal(juros_percentual)
    honorarios_percent = Decimal(honorarios_percent)

    _validar_parametros(valor_principal, data_inicio, data_fim)

    meses_ref = list(_iterar_meses(data_inicio, data_fim))
    if juros_tipo == 'selic':
        return _calcular_selic_integral(
            valor_principal=valor_principal,
            meses_ref=meses_ref,
            multa_523=multa_523,
            honorarios_sucumb=honorarios_sucumb,
            honorarios_percent=honorarios_percent,
        )

    indices_correcao = _indices_por_mes(indice_correcao, meses_ref)
    indices_juros = _indices_por_mes('taxa_legal', meses_ref) if juros_tipo == 'taxa_legal' else {}

    fator_correcao = UM
    fator_juros = UM
    juros_acumulado = ZERO
    tabela_mensal = []

    for posicao, mes_ref in enumerate(meses_ref, start=1):
        indice_mensal = indices_correcao.get(mes_ref, ZERO)
        fator_correcao *= _fator_percentual(indice_mensal)
        valor_corrigido_mes = valor_principal * fator_correcao

        if juros_tipo == 'taxa_legal':
            juros_mensal = indices_juros.get(mes_ref, ZERO)
            juros_anterior = juros_acumulado
            fator_juros *= _fator_percentual(juros_mensal)
            juros_acumulado = valor_corrigido_mes * (fator_juros - UM)
            juros_mes = juros_acumulado - juros_anterior
        else:
            taxa_juros = _taxa_juros_simples(juros_tipo, juros_percentual)
            juros_acumulado_mes = valor_corrigido_mes * (taxa_juros / CEM) * Decimal(posicao)
            juros_mes = juros_acumulado_mes - juros_acumulado
            juros_acumulado = juros_acumulado_mes

        tabela_mensal.append({
            'mes': f'{mes_ref:%m/%Y}',
            'indice_mensal': _arredondar_percentual(indice_mensal),
            'correcao_acumulada': _arredondar_fator(fator_correcao),
            'valor_corrigido': _arredondar_moeda(valor_corrigido_mes),
            'juros_mes': _arredondar_moeda(juros_mes),
            'juros_acumulado': _arredondar_moeda(juros_acumulado),
            'subtotal': _arredondar_moeda(valor_corrigido_mes + juros_acumulado),
        })

    valor_corrigido = valor_principal * fator_correcao
    juros_valor = juros_acumulado
    subtotal = valor_corrigido + juros_valor
    multa_valor = subtotal * Decimal('0.10') if multa_523 else ZERO
    base_honorarios = subtotal + multa_valor
    honorarios_valor = base_honorarios * (honorarios_percent / CEM) if honorarios_sucumb else ZERO
    total = subtotal + multa_valor + honorarios_valor

    return {
        'valor_principal': _arredondar_moeda(valor_principal),
        'valor_corrigido': _arredondar_moeda(valor_corrigido),
        'correcao_acumulada_percent': _arredondar_percentual((fator_correcao - UM) * CEM),
        'juros_valor': _arredondar_moeda(juros_valor),
        'juros_acumulado_percent': _arredondar_percentual(_percentual_juros(valor_corrigido, juros_valor)),
        'subtotal': _arredondar_moeda(subtotal),
        'multa_valor': _arredondar_moeda(multa_valor),
        'honorarios_valor': _arredondar_moeda(honorarios_valor),
        'total': _arredondar_moeda(total),
        'meses': len(meses_ref),
        'tabela_mensal': tabela_mensal,
    }


def calcular_debito_multiplo(
    parcelas: list[dict],
    data_fim: date,
    indice_correcao: str,
    juros_tipo: str,
    juros_percentual: Decimal = Decimal('1.00'),
    multa_523: bool = False,
    honorarios_sucumb: bool = False,
    honorarios_percent: Decimal = Decimal('10.00'),
) -> dict:
    """
    Calcula múltiplos créditos individualmente e consolida.
    """
    if not parcelas:
        raise ValueError('Informe ao menos uma parcela.')

    juros_percentual = Decimal(juros_percentual)
    honorarios_percent = Decimal(honorarios_percent)
    parcelas_resultado = []
    valor_principal_total = ZERO
    valor_corrigido_total = ZERO
    juros_total = ZERO

    for parcela in parcelas:
        valor = Decimal(parcela['valor'])
        data_inicio = parcela['data']
        descricao = parcela.get('descricao', '')
        resultado = calcular_debito(
            valor_principal=valor,
            data_inicio=data_inicio,
            data_fim=data_fim,
            indice_correcao=indice_correcao,
            juros_tipo=juros_tipo,
            juros_percentual=juros_percentual,
            multa_523=False,
            honorarios_sucumb=False,
            honorarios_percent=honorarios_percent,
        )

        valor_principal_total += resultado['valor_principal']
        valor_corrigido_total += resultado['valor_corrigido']
        juros_total += resultado['juros_valor']
        parcelas_resultado.append({
            'descricao': descricao,
            'valor_principal': resultado['valor_principal'],
            'data_inicio': data_inicio,
            'valor_corrigido': resultado['valor_corrigido'],
            'juros_valor': resultado['juros_valor'],
            'subtotal': resultado['subtotal'],
        })

    subtotal = valor_corrigido_total + juros_total
    multa_valor = subtotal * Decimal('0.10') if multa_523 else ZERO
    base_honorarios = subtotal + multa_valor
    honorarios_valor = base_honorarios * (honorarios_percent / CEM) if honorarios_sucumb else ZERO
    total = subtotal + multa_valor + honorarios_valor

    return {
        'parcelas': parcelas_resultado,
        'consolidado': {
            'valor_principal_total': _arredondar_moeda(valor_principal_total),
            'valor_corrigido_total': _arredondar_moeda(valor_corrigido_total),
            'juros_total': _arredondar_moeda(juros_total),
            'subtotal': _arredondar_moeda(subtotal),
            'multa_valor': _arredondar_moeda(multa_valor),
            'honorarios_valor': _arredondar_moeda(honorarios_valor),
            'total': _arredondar_moeda(total),
        },
    }


def comparar_cenarios(
    valor_principal: Decimal,
    data_inicio: date,
    data_fim: date,
    cenarios: list[dict],
    multa_523: bool = False,
    honorarios_sucumb: bool = False,
    honorarios_percent: Decimal = Decimal('10.00'),
) -> dict:
    """
    Calcula o mesmo débito com diferentes índices e juros.
    """
    if len(cenarios) < 2 or len(cenarios) > 3:
        raise ValueError('Informe de 2 a 3 cenários para comparação.')

    resultados = []
    for posicao, cenario in enumerate(cenarios, start=1):
        resultado = calcular_debito(
            valor_principal=valor_principal,
            data_inicio=data_inicio,
            data_fim=data_fim,
            indice_correcao=cenario.get('indice_correcao') or 'ipca_e',
            juros_tipo=cenario.get('juros_tipo') or 'simples_1',
            juros_percentual=Decimal(cenario.get('juros_percentual', Decimal('1.00'))),
            multa_523=multa_523,
            honorarios_sucumb=honorarios_sucumb,
            honorarios_percent=honorarios_percent,
        )
        resultados.append({
            'nome': cenario.get('nome') or f'Cenário {posicao}',
            'resultado': resultado,
        })

    maior = max(resultados, key=lambda item: item['resultado']['total'])
    menor = min(resultados, key=lambda item: item['resultado']['total'])
    diferenca = maior['resultado']['total'] - menor['resultado']['total']
    diferenca_percent = ZERO
    if menor['resultado']['total'] != ZERO:
        diferenca_percent = (diferenca / menor['resultado']['total']) * CEM

    return {
        'cenarios': resultados,
        'comparativo': {
            'maior_total': {
                'nome': maior['nome'],
                'valor': maior['resultado']['total'],
            },
            'menor_total': {
                'nome': menor['nome'],
                'valor': menor['resultado']['total'],
            },
            'diferenca': _arredondar_moeda(diferenca),
            'diferenca_percent': _arredondar_percentual(diferenca_percent),
        },
    }


def _calcular_selic_integral(
    valor_principal,
    meses_ref,
    multa_523,
    honorarios_sucumb,
    honorarios_percent,
):
    indices_selic = _indices_por_mes('selic', meses_ref)
    fator_selic = UM
    tabela_mensal = []

    for mes_ref in meses_ref:
        indice_mensal = indices_selic.get(mes_ref, ZERO)
        fator_selic *= _fator_percentual(indice_mensal)
        valor_com_selic = valor_principal * fator_selic
        juros_acumulado = valor_com_selic - valor_principal

        tabela_mensal.append({
            'mes': f'{mes_ref:%m/%Y}',
            'indice_mensal': _arredondar_percentual(indice_mensal),
            'correcao_acumulada': _arredondar_fator(fator_selic),
            'valor_corrigido': _arredondar_moeda(valor_com_selic),
            'juros_mes': _arredondar_moeda(ZERO),
            'juros_acumulado': _arredondar_moeda(juros_acumulado),
            'subtotal': _arredondar_moeda(valor_com_selic),
        })

    valor_com_selic = valor_principal * fator_selic
    juros_valor = valor_com_selic - valor_principal
    subtotal = valor_com_selic
    multa_valor = subtotal * Decimal('0.10') if multa_523 else ZERO
    base_honorarios = subtotal + multa_valor
    honorarios_valor = base_honorarios * (Decimal(honorarios_percent) / CEM) if honorarios_sucumb else ZERO
    total = subtotal + multa_valor + honorarios_valor

    return {
        'valor_principal': _arredondar_moeda(valor_principal),
        'valor_corrigido': _arredondar_moeda(valor_com_selic),
        'correcao_acumulada_percent': _arredondar_percentual((fator_selic - UM) * CEM),
        'juros_valor': _arredondar_moeda(juros_valor),
        'juros_acumulado_percent': _arredondar_percentual((fator_selic - UM) * CEM),
        'subtotal': _arredondar_moeda(subtotal),
        'multa_valor': _arredondar_moeda(multa_valor),
        'honorarios_valor': _arredondar_moeda(honorarios_valor),
        'total': _arredondar_moeda(total),
        'meses': len(meses_ref),
        'tabela_mensal': tabela_mensal,
    }


def _validar_parametros(valor_principal, data_inicio, data_fim):
    if valor_principal <= ZERO:
        raise ValueError('O valor principal deve ser maior que zero.')
    if data_inicio > data_fim:
        raise ValueError('A data inicial deve ser menor ou igual a data final.')


def _indices_por_mes(tipo, meses_ref):
    if not meses_ref:
        return {}

    indices = IndiceEconomico.objects.filter(
        tipo=tipo,
        data__gte=meses_ref[0],
        data__lte=meses_ref[-1],
    ).order_by('data')
    return {indice.data: indice.valor for indice in indices}


def _iterar_meses(data_inicio, data_fim):
    atual = date(data_inicio.year, data_inicio.month, 1)
    limite = date(data_fim.year, data_fim.month, 1)

    while atual <= limite:
        yield atual
        if atual.month == 12:
            atual = date(atual.year + 1, 1, 1)
        else:
            atual = date(atual.year, atual.month + 1, 1)


def _fator_percentual(valor_percentual):
    return UM + (Decimal(valor_percentual) / CEM)


def _taxa_juros_simples(juros_tipo, juros_percentual):
    taxas = {
        'simples_1': Decimal('1.00'),
        'simples_05': Decimal('0.50'),
        'customizado': Decimal(juros_percentual),
    }
    try:
        return taxas[juros_tipo]
    except KeyError as exc:
        raise ValueError(f'Tipo de juros invalido: {juros_tipo}') from exc


def _percentual_juros(valor_corrigido, juros_valor):
    if valor_corrigido == ZERO:
        return ZERO
    return (juros_valor / valor_corrigido) * CEM


def _arredondar_moeda(valor):
    return Decimal(valor).quantize(MOEDA, rounding=ROUND_HALF_UP)


def _arredondar_percentual(valor):
    return Decimal(valor).quantize(PERCENTUAL, rounding=ROUND_HALF_UP)


def _arredondar_fator(valor):
    return Decimal(valor).quantize(FATOR, rounding=ROUND_HALF_UP)

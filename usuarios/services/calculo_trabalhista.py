from datetime import date
from decimal import Decimal, ROUND_HALF_UP


MOEDA = Decimal('0.01')
ZERO = Decimal('0')
CEM = Decimal('100')


def calcular_verbas_trabalhistas(
    salario_base: Decimal,
    data_admissao: date,
    data_demissao: date,
    tipo_demissao: str,
    horas_extras_50: int = 0,
    horas_extras_100: int = 0,
    meses_trabalhados: int = 0,
    aviso_previo: str = 'indenizado',
    saldo_fgts: Decimal = Decimal('0'),
) -> dict:
    """
    Calcula verbas rescisórias trabalhistas.
    """
    salario_base = Decimal(salario_base)
    saldo_fgts = Decimal(saldo_fgts or ZERO)
    horas_extras_50 = int(horas_extras_50 or 0)
    horas_extras_100 = int(horas_extras_100 or 0)

    if salario_base <= ZERO:
        raise ValueError('O salário base deve ser maior que zero.')
    if data_admissao > data_demissao:
        raise ValueError('A data de admissão deve ser menor ou igual à data de demissão.')
    if tipo_demissao not in ('sem_justa_causa', 'com_justa_causa', 'pedido_demissao'):
        raise ValueError('Tipo de demissão inválido.')

    meses_total = int(meses_trabalhados or 0) or _meses_trabalhados(data_admissao, data_demissao)
    verbas = []

    saldo_salario = (salario_base / Decimal('30')) * Decimal(data_demissao.day)
    verbas.append({
        'nome': 'Saldo de salário',
        'dias': data_demissao.day,
        'valor': _moeda(saldo_salario),
    })

    avos_13 = _avos_ano_demissao(data_admissao, data_demissao)
    if tipo_demissao != 'com_justa_causa' and avos_13:
        valor_13 = (salario_base / Decimal('12')) * Decimal(avos_13)
        verbas.append({
            'nome': '13º proporcional',
            'avos': avos_13,
            'valor': _moeda(valor_13),
        })

    avos_ferias = _avos_ferias(data_admissao, data_demissao)
    if tipo_demissao != 'com_justa_causa' or meses_total >= 12:
        ferias = (salario_base / Decimal('12')) * Decimal(avos_ferias)
        ferias = _moeda(ferias)
        verbas.append({
            'nome': 'Férias proporcionais',
            'avos': avos_ferias,
            'valor': ferias,
        })
        verbas.append({
            'nome': '1/3 constitucional',
            'base': ferias,
            'valor': _moeda(ferias / Decimal('3')),
        })

    if tipo_demissao == 'sem_justa_causa' and aviso_previo == 'indenizado':
        dias_aviso = min(Decimal('90'), Decimal('30') + (Decimal('3') * Decimal(_anos_completos(data_admissao, data_demissao))))
        verbas.append({
            'nome': 'Aviso prévio indenizado',
            'dias': int(dias_aviso),
            'valor': _moeda((salario_base / Decimal('30')) * dias_aviso),
        })

    valor_hora = salario_base / Decimal('220')
    horas_50_valor = _moeda(valor_hora * Decimal('1.5') * Decimal(horas_extras_50))
    horas_100_valor = _moeda(valor_hora * Decimal('2.0') * Decimal(horas_extras_100))
    if horas_extras_50:
        verbas.append({
            'nome': 'Horas extras 50%',
            'horas': horas_extras_50,
            'valor': horas_50_valor,
        })
    if horas_extras_100:
        verbas.append({
            'nome': 'Horas extras 100%',
            'horas': horas_extras_100,
            'valor': horas_100_valor,
        })

    total_he = horas_50_valor + horas_100_valor
    if total_he > ZERO:
        verbas.append({
            'nome': 'DSR sobre horas extras',
            'valor': _moeda(total_he / Decimal('6')),
        })

    if tipo_demissao == 'sem_justa_causa':
        base_fgts = saldo_fgts if saldo_fgts > ZERO else salario_base * Decimal('0.08') * Decimal(meses_total)
        verbas.append({
            'nome': 'Multa 40% FGTS',
            'base': _moeda(base_fgts),
            'valor': _moeda(base_fgts * Decimal('0.40')),
        })

    total_bruto = _moeda(sum((verba['valor'] for verba in verbas), ZERO))
    inss = _calcular_inss_2024(total_bruto)
    irrf = _calcular_irrf_2024(total_bruto - inss)
    deducoes = [
        {'nome': 'INSS (estimativa)', 'valor': inss},
        {'nome': 'IRRF (estimativa)', 'valor': irrf},
    ]
    total_liquido = _moeda(total_bruto - inss - irrf)

    return {
        'dados_entrada': {
            'salario_base': _moeda(salario_base),
            'data_admissao': data_admissao,
            'data_demissao': data_demissao,
            'tipo_demissao': tipo_demissao,
            'meses_trabalhados': meses_total,
        },
        'verbas': verbas,
        'total_bruto': total_bruto,
        'deducoes': deducoes,
        'total_liquido': total_liquido,
        'aviso': 'Valores estimados. Consulte contador.',
    }


def _meses_trabalhados(data_admissao, data_demissao):
    meses = (data_demissao.year - data_admissao.year) * 12 + data_demissao.month - data_admissao.month + 1
    return max(meses, 0)


def _avos_ano_demissao(data_admissao, data_demissao):
    inicio = data_admissao if data_admissao.year == data_demissao.year else date(data_demissao.year, 1, 1)
    avos = 0
    for mes in range(inicio.month, data_demissao.month + 1):
        primeiro_dia = date(data_demissao.year, mes, 1)
        inicio_mes = max(inicio, primeiro_dia)
        if mes == data_demissao.month:
            fim_mes = data_demissao
        else:
            fim_mes = _ultimo_dia_mes(data_demissao.year, mes)
        if (fim_mes - inicio_mes).days + 1 >= 15:
            avos += 1
    return min(avos, 12)


def _avos_ferias(data_admissao, data_demissao):
    meses_total = _meses_trabalhados(data_admissao, data_demissao)
    avos = meses_total % 12
    if avos == 0 and meses_total > 0:
        avos = 12
    return avos


def _anos_completos(data_admissao, data_demissao):
    anos = data_demissao.year - data_admissao.year
    if (data_demissao.month, data_demissao.day) < (data_admissao.month, data_admissao.day):
        anos -= 1
    return max(anos, 0)


def _ultimo_dia_mes(ano, mes):
    if mes == 12:
        return date(ano, 12, 31)
    return date(ano, mes + 1, 1).replace(day=1) - _um_dia()


def _um_dia():
    from datetime import timedelta
    return timedelta(days=1)


def _calcular_inss_2024(base):
    faixas = [
        (Decimal('1412.00'), Decimal('0.075')),
        (Decimal('2666.68'), Decimal('0.09')),
        (Decimal('4000.03'), Decimal('0.12')),
        (Decimal('7786.02'), Decimal('0.14')),
    ]
    anterior = ZERO
    total = ZERO
    for limite, aliquota in faixas:
        if base <= anterior:
            break
        tributavel = min(base, limite) - anterior
        if tributavel > ZERO:
            total += tributavel * aliquota
        anterior = limite
    return _moeda(total)


def _calcular_irrf_2024(base):
    faixas = [
        (Decimal('2259.20'), Decimal('0'), Decimal('0')),
        (Decimal('2826.65'), Decimal('0.075'), Decimal('169.44')),
        (Decimal('3751.05'), Decimal('0.15'), Decimal('381.44')),
        (Decimal('4664.68'), Decimal('0.225'), Decimal('662.77')),
    ]
    if base <= faixas[0][0]:
        return ZERO
    for limite, aliquota, deducao in faixas[1:]:
        if base <= limite:
            return _moeda(max((base * aliquota) - deducao, ZERO))
    return _moeda(max((base * Decimal('0.275')) - Decimal('896.00'), ZERO))


def _moeda(valor):
    return Decimal(valor).quantize(MOEDA, rounding=ROUND_HALF_UP)

from datetime import date


TABELAS_TJ = {
    'tjsp': {
        'nome': 'Tabela Prática TJSP',
        'periodos': [
            (date(1994, 7, 1), date(1995, 12, 31), 'igpm'),
            (date(1996, 1, 1), date(2006, 3, 31), 'igpm'),
            (date(2006, 4, 1), date(2023, 12, 31), 'ipca_e'),
            (date(2024, 1, 1), date(2099, 12, 31), 'ipca_e'),
        ],
    },
    'tjrj': {
        'nome': 'Tabela Prática TJRJ',
        'periodos': [
            (date(1994, 7, 1), date(2004, 3, 31), 'igpm'),
            (date(2004, 4, 1), date(2023, 12, 31), 'ipca_e'),
            (date(2024, 1, 1), date(2099, 12, 31), 'ipca_e'),
        ],
    },
    'tjmg': {
        'nome': 'Tabela Prática TJMG',
        'periodos': [
            (date(1994, 7, 1), date(2009, 12, 31), 'igpm'),
            (date(2010, 1, 1), date(2023, 12, 31), 'inpc'),
            (date(2024, 1, 1), date(2099, 12, 31), 'ipca_e'),
        ],
    },
    'tjpr': {
        'nome': 'Tabela Prática TJPR',
        'periodos': [
            (date(1994, 7, 1), date(2009, 12, 31), 'inpc'),
            (date(2010, 1, 1), date(2023, 12, 31), 'ipca_e'),
            (date(2024, 1, 1), date(2099, 12, 31), 'ipca_e'),
        ],
    },
    'tjrs': {
        'nome': 'Tabela Prática TJRS',
        'periodos': [
            (date(1994, 7, 1), date(2009, 12, 31), 'igpm'),
            (date(2010, 1, 1), date(2023, 12, 31), 'ipca_e'),
            (date(2024, 1, 1), date(2099, 12, 31), 'ipca_e'),
        ],
    },
    'cjf': {
        'nome': 'Tabela CJF (Justiça Federal)',
        'periodos': [
            (date(1994, 7, 1), date(2009, 12, 31), 'ipca_e'),
            (date(2010, 1, 1), date(2099, 12, 31), 'ipca_e'),
        ],
    },
    'tst': {
        'nome': 'Tabela TST (Débitos Trabalhistas)',
        'periodos': [
            (date(1994, 7, 1), date(2021, 11, 30), 'ipca_e'),
            (date(2021, 12, 1), date(2099, 12, 31), 'selic'),
        ],
    },
}


def obter_indice_por_periodo(tribunal: str, data: date) -> str:
    """Retorna o tipo de índice correto para o tribunal e data."""
    tabela = TABELAS_TJ.get(tribunal)
    if not tabela:
        return 'ipca_e'
    for inicio, fim, indice in tabela['periodos']:
        if inicio <= data <= fim:
            return indice
    return 'ipca_e'


def listar_tribunais_disponiveis() -> list[dict]:
    """Retorna lista de tribunais com nome e código."""
    return [
        {'codigo': codigo, 'nome': tabela['nome']}
        for codigo, tabela in TABELAS_TJ.items()
    ]

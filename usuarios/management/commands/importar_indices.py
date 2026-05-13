import time

from django.core.management.base import BaseCommand, CommandError

from usuarios.services.indices import (
    SERIES_BCB,
    ImportacaoIndicesError,
    importar_indices_bcb,
)


class Command(BaseCommand):
    help = 'Importa indices economicos historicos via API SGS do Banco Central.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--indice',
            choices=SERIES_BCB.keys(),
            help='Importa apenas um indice especifico.',
        )
        parser.add_argument(
            '--ano-inicio',
            type=int,
            default=1994,
            help='Ano inicial da importacao (default: 1994).',
        )

    def handle(self, *args, **options):
        inicio_execucao = time.perf_counter()
        indice = options.get('indice')
        tipos = [indice] if indice else None

        try:
            resultado = importar_indices_bcb(
                tipos=tipos,
                ano_inicio=options['ano_inicio'],
                output=self.stdout,
            )
        except ImportacaoIndicesError as exc:
            raise CommandError(str(exc)) from exc

        tempo_total = time.perf_counter() - inicio_execucao
        total = sum(resultado.values())
        self.stdout.write(f'Total de registros novos: {total}')
        self.stdout.write(self.style.SUCCESS(f'Tempo total: {tempo_total:.2f}s'))

from django.apps import AppConfig


def _criar_schedule_datajud(sender, **kwargs):
    """Garante que o schedule diário do DataJud existe após cada migrate."""
    try:
        from django_q.models import Schedule
        Schedule.objects.get_or_create(
            name='Atualizar processos DataJud',
            defaults={
                'func': 'ia.tasks.atualizar_todos_processos_datajud',
                'schedule_type': 'D',
                'repeats': -1,
            },
        )
    except Exception:
        pass


def _criar_schedule_alertas_honorarios(sender, **kwargs):
    """Garante que o schedule diário de alertas de honorários existe após cada migrate."""
    try:
        from django_q.models import Schedule
        Schedule.objects.get_or_create(
            name='Alertar honorários atrasados',
            defaults={
                'func': 'ia.tasks.alertar_honorarios_atrasados',
                'schedule_type': 'D',
                'repeats': -1,
            },
        )
    except Exception:
        pass


class IaConfig(AppConfig):
    name = 'ia'

    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(_criar_schedule_datajud, sender=self)
        post_migrate.connect(_criar_schedule_alertas_honorarios, sender=self)

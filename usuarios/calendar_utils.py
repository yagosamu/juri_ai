"""
Utilitário de integração com Google Calendar para prazos.
Todas as funções falham silenciosamente se token.json não existir ou a API retornar erro.
"""
import os
import datetime
from django.conf import settings

_TOKEN_PATH = os.path.join(settings.BASE_DIR, 'token.json')


def _get_service():
    """Retorna o serviço Google Calendar autenticado, ou None se não configurado."""
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        if not os.path.exists(_TOKEN_PATH):
            return None

        creds = Credentials.from_authorized_user_file(_TOKEN_PATH)
        return build('calendar', 'v3', credentials=creds)
    except Exception:
        return None


def _body_evento(prazo):
    return {
        'summary': f'[{prazo.get_tipo_display()}] {prazo.descricao}',
        'description': (
            f'Processo: {prazo.processo}\n'
            f'Cliente: {prazo.processo.cliente}\n'
            f'Status: {prazo.get_status_display()}'
        ),
        'start': {'date': prazo.data_prazo.isoformat()},
        'end':   {'date': prazo.data_prazo.isoformat()},
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'email',  'minutes': prazo.alerta_dias_antes * 24 * 60},
                {'method': 'popup',  'minutes': prazo.alerta_dias_antes * 24 * 60},
            ],
        },
    }


def criar_evento_prazo(prazo) -> str:
    """Cria evento no Google Calendar. Retorna event_id ou '' em caso de falha."""
    try:
        service = _get_service()
        if service is None:
            return ''
        result = service.events().insert(
            calendarId='primary',
            body=_body_evento(prazo),
        ).execute()
        return result.get('id', '')
    except Exception:
        return ''


def atualizar_evento_prazo(prazo) -> None:
    """Atualiza evento existente. Silencioso se não configurado ou sem event_id."""
    try:
        if not prazo.google_event_id:
            return
        service = _get_service()
        if service is None:
            return
        service.events().update(
            calendarId='primary',
            eventId=prazo.google_event_id,
            body=_body_evento(prazo),
        ).execute()
    except Exception:
        pass


def cancelar_evento_prazo(prazo) -> None:
    """Deleta evento do Google Calendar. Silencioso se não configurado ou sem event_id."""
    try:
        if not prazo.google_event_id:
            return
        service = _get_service()
        if service is None:
            return
        service.events().delete(
            calendarId='primary',
            eventId=prazo.google_event_id,
        ).execute()
    except Exception:
        pass

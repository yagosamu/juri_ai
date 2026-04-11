from django import template
from usuarios.models import Lead

register = template.Library()


@register.simple_tag(takes_context=True)
def leads_novos(context):
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return 0
    return Lead.objects.filter(user=request.user, status='novo').count()

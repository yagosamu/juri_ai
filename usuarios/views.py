from django.contrib.auth import authenticate
from django.contrib import auth, messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.messages import constants
from django.contrib import messages
from django.contrib.auth.models import User
from .models import Cliente, Documentos, ConfiguracaoWhatsApp, ConsentimentoLGPD
from ia.models import AnaliseJurisprudencia
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.conf import settings
import datetime
import os



def home(request):
    return render(request, 'home.html')


def privacidade(request):
    return render(request, 'privacidade.html')


def termos(request):
    return render(request, 'termos.html')


def cadastro(request):
    if request.method == 'GET':
        return render(request, 'cadastro.html')
    elif request.method == 'POST':
        username = request.POST.get('username')
        senha = request.POST.get('senha')
        confirmar_senha = request.POST.get('confirmar_senha')
        aceito_termos = request.POST.get('aceito_termos')

        if not aceito_termos:
            messages.add_message(request, constants.ERROR, 'Você precisa aceitar os Termos de Uso e a Política de Privacidade para criar uma conta.')
            return redirect('cadastro')

        if not senha == confirmar_senha:
            messages.add_message(request, constants.ERROR, 'Senha e confirmar senha não são iguais.')
            return redirect('cadastro')

        if len(senha) < 6:
            messages.add_message(request, constants.ERROR, 'Sua senha deve ter pelo meno 6 caracteres.')
            return redirect('cadastro')

        users = User.objects.filter(username=username)

        if users.exists():
            messages.add_message(request, constants.ERROR, 'Já existe um usuário com esse username.')
            return redirect('cadastro')

        user = User.objects.create_user(
            username=username,
            password=senha
        )

        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
        if ip and ',' in ip:
            ip = ip.split(',')[0].strip()
        ConsentimentoLGPD.objects.create(user=user, versao='1.0', ip=ip)

        return redirect('login')


def login(request):
    if request.method == 'GET':
        return render(request, 'login.html')
    elif request.method == 'POST':
        username = request.POST.get('username')
        senha = request.POST.get('senha')
        
        user = authenticate(request, username=username, password=senha)
        if user is not None:
            auth.login(request, user)
            return redirect('dashboard')
        else:
            messages.add_message(request, constants.ERROR, 'Usuário ou senha inválidos.')
            return redirect('login')


def _get_proximos_eventos():
    """Busca os próximos 5 eventos do Google Calendar. Retorna [] se não configurado."""
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        token_path = os.path.join(settings.BASE_DIR, 'token.json')
        if not os.path.exists(token_path):
            return []

        creds = Credentials.from_authorized_user_file(token_path)
        service = build('calendar', 'v3', credentials=creds)

        agora = datetime.datetime.utcnow().isoformat() + 'Z'
        resultado = service.events().list(
            calendarId='primary',
            timeMin=agora,
            maxResults=5,
            singleEvents=True,
            orderBy='startTime',
        ).execute()
        return resultado.get('items', [])
    except Exception:
        return []


@login_required
def dashboard(request):
    clientes_qs = Cliente.objects.filter(user=request.user)
    documentos_qs = Documentos.objects.filter(cliente__user=request.user)

    total_clientes    = clientes_qs.count()
    clientes_ativos   = clientes_qs.filter(status=True).count()
    clientes_inativos = clientes_qs.filter(status=False).count()

    total_documentos        = documentos_qs.count()
    documentos_processados  = documentos_qs.exclude(content='').count()

    alertas = (AnaliseJurisprudencia.objects
               .filter(documento__cliente__user=request.user,
                       classificacao__in=['Alto', 'Crítico'])
               .select_related('documento', 'documento__cliente')
               .order_by('-data_criacao')[:5])

    proximos_eventos = _get_proximos_eventos()

    return render(request, 'dashboard.html', {
        'total_clientes': total_clientes,
        'clientes_ativos': clientes_ativos,
        'clientes_inativos': clientes_inativos,
        'total_documentos': total_documentos,
        'documentos_processados': documentos_processados,
        'alertas': alertas,
        'proximos_eventos': proximos_eventos,
    })


@login_required
def clientes(request):
    if request.method == 'GET':
        clientes = Cliente.objects.filter(user=request.user)
        return render(request, 'clientes.html', {'clientes': clientes})
    elif request.method == 'POST':
        nome = request.POST.get('nome')
        email = request.POST.get('email')
        tipo = request.POST.get('tipo')
        status = request.POST.get('status') == 'on'
        
        Cliente.objects.create(
            nome=nome,
            email=email,
            tipo=tipo,
            status=status,
            user=request.user
        )
        
        messages.add_message(request, constants.SUCCESS, 'Cliente cadastrado com sucesso!')
        return redirect('clientes')
    

@login_required
def cliente(request, id):
    cliente = get_object_or_404(Cliente, id=id, user=request.user)
    if request.method == 'GET':
        documentos = Documentos.objects.filter(cliente=cliente)
        return render(request, 'cliente.html', {'cliente': cliente, 'documentos': documentos})
    elif request.method == 'POST':
        tipo = request.POST.get('tipo')
        documento = request.FILES.get('documento')
        data = request.POST.get('data')

        documentos = Documentos(
            cliente=cliente,
            tipo=tipo,
            arquivo=documento,
            data_upload=data
        )
        documentos.save()

        return redirect(reverse('cliente', kwargs={'id': cliente.id}))


@login_required
def configuracao_whatsapp(request):
    config = ConfiguracaoWhatsApp.objects.filter(user=request.user).first()
    if request.method == 'GET':
        return render(request, 'configuracao_whatsapp.html', {'config': config})
    elif request.method == 'POST':
        base_url = request.POST.get('base_url')
        instancia = request.POST.get('instancia')
        api_key = request.POST.get('api_key')

        if config:
            config.base_url = base_url
            config.instancia = instancia
            if api_key:
                config.api_key = api_key
            config.save()
        else:
            ConfiguracaoWhatsApp.objects.create(
                user=request.user,
                base_url=base_url,
                instancia=instancia,
                api_key=api_key,
            )

        messages.add_message(request, constants.SUCCESS, 'Configuração salva com sucesso!')
        return redirect('configuracao_whatsapp')


@login_required
def excluir_conta(request):
    if request.method == 'GET':
        return render(request, 'excluir_conta.html')

    senha_confirmacao = request.POST.get('senha_confirmacao')
    user = authenticate(request, username=request.user.username, password=senha_confirmacao)

    if user is None:
        messages.add_message(request, constants.ERROR, 'Senha incorreta. A conta não foi excluída.')
        return redirect('excluir_conta')

    # Tenta limpar registros no LanceDB silenciosamente antes de deletar o User
    try:
        import lancedb
        from django.conf import settings as django_settings
        import os

        lancedb_path = os.path.join(django_settings.BASE_DIR, 'lancedb')
        db = lancedb.connect(lancedb_path)

        cliente_ids = list(
            Cliente.objects.filter(user=user).values_list('id', flat=True)
        )
        if cliente_ids and 'documentos' in db.table_names():
            table = db.open_table('documentos')
            ids_str = ', '.join(str(cid) for cid in cliente_ids)
            table.delete(f"cliente_id IN ({ids_str})")
    except Exception:
        pass  # Falha no LanceDB não bloqueia a exclusão da conta

    # Deleta dados do usuário (CASCADE cobre: Cliente → Documentos, ConfiguracaoWhatsApp, ConsentimentoLGPD)
    auth.logout(request)
    user.delete()

    messages.add_message(request, constants.SUCCESS, 'Sua conta foi excluída com sucesso.')
    return redirect('home')


@login_required
def logout(request):
    auth.logout(request)
    return redirect('login')

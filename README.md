# JuriAI

SaaS jurídico para advogados brasileiros, com gestão de clientes, processos, prazos, financeiro, documentos e agentes de IA.

## Setup local

1. Crie e ative o ambiente virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Instale as dependências:

```powershell
python -m pip install -r requirements.txt
```

3. Copie o exemplo de ambiente e preencha as chaves locais:

```powershell
Copy-Item .env.example .env
```

4. Rode as migrações e o servidor:

```powershell
python manage.py migrate
python manage.py runserver
```

5. Em outro terminal, rode o worker para processar documentos:

```powershell
.\.venv\Scripts\Activate.ps1
python manage.py qcluster
```

## Verificações úteis

```powershell
python manage.py check
python manage.py test
```

## Dados sensíveis

Não commite `.env`, banco local, backups, tokens OAuth, `client_secret.json`, `media/`, `lancedb/` ou qualquer arquivo com dados reais de clientes.

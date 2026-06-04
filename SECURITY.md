# Security Policy

## Como reportar vulnerabilidades

Se encontrar uma vulnerabilidade no JuriAI, não abra issue pública com detalhes exploráveis.

Envie um e-mail para o mantenedor do projeto com:

- descrição do problema;
- passos mínimos para reproduzir;
- impacto esperado;
- arquivos/rotas afetados, se souber.

## Escopo

Estão em escopo:

- vazamento de dados de clientes;
- falhas de autenticação ou autorização;
- exposição de credenciais;
- upload inseguro de arquivos;
- problemas em webhooks e integrações.

## Boas práticas para contributors

- Nunca commite secrets.
- Use `.env.example` como referência.
- Rode `python manage.py check` antes de abrir PR.
- Evite logs contendo prompts, documentos, dados pessoais ou conteúdo jurídico de clientes.

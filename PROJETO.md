# Saulo Curso — Documentação do Projeto

Plataforma de venda e entrega de cursos online. Django + Tailwind (CDN) + Supabase (Postgres).
Este documento existe pra qualquer pessoa (ou IA) entender o projeto do zero, sem precisar reler a conversa inteira que o gerou.

---

## 1. Visão geral

- Cliente compra curso → paga (mock) → cadastra (nome/CPF/telefone/email) → recebe senha temporária por email (mock) → troca senha no primeiro acesso → acessa aulas (vídeo + PDF) → marca aulas concluídas → ganha certificado ao completar 100%.
- Admin cadastra cursos/módulos/aulas/mentorias por um **painel próprio** (não é o Django admin) e edita textos da home por uma tela de **Configurações do site**.
- Vídeos/PDFs podem vir do **YouTube**, do **Google Drive** (ID colado manualmente) ou de **upload local** — com proteções pra dificultar cópia/link direto.

---

## 2. Stack

- Django 6.0 (Python 3.13), function-based views em quase tudo
- Tailwind CSS via **CDN** (Play CDN) — sem build step, prototípico de propósito
- Banco: **Supabase Postgres** (produção/atual) — local cai pra SQLite se `DATABASE_URL` não estiver setado
- `django-environ` pra config via `.env`
- Sem REST framework, sem JS framework — só fetch() + DOM puro nos pontos que precisam (player de vídeo/pdf)

---

## 3. Apps Django

| App | Responsabilidade |
|---|---|
| `config` | settings, urls raiz |
| `accounts` | `Perfil` (extra do User), login, troca de senha obrigatória, middleware |
| `cursos` | Curso, Módulo, Aula, Mentoria, ConfiguracaoSite, ContatoMensagem — views públicas + **painel próprio** (`views_painel.py`, `urls_painel.py`, `forms_painel.py`) |
| `matriculas` | Matricula (aluno×curso), AulaConcluida, Certificado, lógica de progresso e controle de acesso (`mixins.py`) |
| `pagamentos` | Pagamento, gateway mock trocável, fluxo de checkout + cadastro pós-pagamento |
| `notificacoes` | NotificacaoLog, serviço de notificação mock (email/whatsapp) trocável |

---

## 4. Modelos principais

**cursos.Curso** — titulo, slug, descricao_curta, descricao, preco, imagem_capa, video_youtube_id, ativo
**cursos.Modulo** — curso FK, titulo, ordem
**cursos.Aula** — modulo FK, titulo, youtube_id, drive_file_id, arquivo_pdf (local), drive_pdf_file_id, ordem
**cursos.MentoriaAoVivo** — curso FK, titulo, descricao, data_hora, link_reuniao
**cursos.ConfiguracaoSite** — singleton (pk=1 via `.obter()`), textos do hero/sobre/contato da home
**cursos.ContatoMensagem** — email, telefone, mensagem (formulário de contato)

**accounts.Perfil** — user OneToOne, telefone, cpf, `deve_trocar_senha` (bool)

**matriculas.Matricula** — aluno FK, curso FK, ativo, data_matricula (unique aluno+curso)
**matriculas.AulaConcluida** — aluno FK, aula FK (unique aluno+aula)
**matriculas.Certificado** — aluno FK, curso FK, codigo (UUID), emitido_em (unique aluno+curso)

**pagamentos.Pagamento** — aluno FK, curso FK, valor, status, metodo (pix/cartao), criado_em

**notificacoes.NotificacaoLog** — canal (email/whatsapp), destinatario, assunto, mensagem, enviado_em

---

## 5. Fluxo de compra (pagamento ANTES do cadastro)

Decisão deliberada: **paga primeiro, cadastra depois**.

1. `GET /pagamentos/checkout/<slug>/` — mostra preço + escolha Pix/Cartão (visual só, sem gateway real)
2. `POST` → `pagamentos.services.get_payment_gateway()` (mock, sempre aprova) →
   - **Se já logado**: cria Pagamento + Matrícula direto, manda pra "Minha área"
   - **Se anônimo**: guarda `curso_id` + `metodo` na sessão, redireciona pra `/pagamentos/cadastro/`
3. `/pagamentos/cadastro/` — formulário nome/CPF/telefone/email (senha NÃO é escolhida pelo usuário)
4. No submit: cria User (username=email) com **senha aleatória gerada** (`secrets.token_urlsafe`), cria Perfil com `deve_trocar_senha=True`, cria Pagamento+Matrícula, loga o usuário automaticamente
5. `NotificationService` dispara (mock) email de "matrícula confirmada" + email com login/senha temporária
6. Middleware `ForcarTrocaSenhaMiddleware` bloqueia qualquer página até o usuário trocar a senha em `/accounts/trocar-senha/`
7. Nessa tela, a senha temporária aparece destacada (com botão "copiar") — **só nessa visita**, some depois de trocada. Isso é modo demonstração (email é mock, não chega de verdade nenhuma caixa de entrada).

Preço só aparece na página de checkout — a página pública do curso (`/cursos/<slug>/`) não mostra valor, só o botão "Quero me inscrever".

---

## 6. Proteção de vídeo/PDF (aulas pagas)

Objetivo: dificultar cópia casual do link/vídeo. **Não é (e não pretende ser) DRM real** — usuário técnico com DevTools sempre consegue algo. Isso foi decidido conscientemente com o cliente.

**Arquitetura**: o ID do vídeo/pdf **nunca aparece no HTML inicial**. A página `/aulas/<id>/` carrega um player vazio; JS busca `/aulas/<id>/video-token/` (e `/pdf-token/`), endpoint protegido por `matricula_required_aula` (só responde se o usuário tem matrícula ativa no curso daquela aula), que devolve `{"fonte": "youtube"|"drive"|"local", ...}`. O JS monta o iframe em runtime.

**Três fontes possíveis por aula** (prioridade: Drive > YouTube para vídeo; Drive > local para PDF):
- `youtube_id` — embed `youtube.com/embed/ID` com `rel=0&modestbranding=1&fs=0&disablekb=1&iv_load_policy=3`. Tem **overlay invisível** (topo 24% + canto inferior-direito) que bloqueia clique no título/badge "Assista no YouTube" — só enquanto o vídeo NÃO está tocando (usa a IFrame API do YouTube pra saber o estado e sumir com o bloqueio durante a reprodução real, senão cobriria os controles).
- `drive_file_id` / `drive_pdf_file_id` — embed `drive.google.com/file/d/ID/preview`. Mesmo overlay (56×56px) no canto superior-direito bloqueando o ícone "abrir em outra janela" do Drive.
- `arquivo_pdf` — upload local, servido por `FileResponse` autenticado (`/aulas/<id>/pdf/`).

**Botão de tela cheia próprio** (`#fullscreen-btn`) — usa a Fullscreen API do navegador no `<div>` que envolve o player, não no iframe. Existe porque o YouTube tem `fs=0` (fullscreen nativo desativado de propósito).

**Importante — YouTube error 153**: desde ~final de 2025 o YouTube exige `referrerpolicy="strict-origin-when-cross-origin"` no iframe, senão o embed quebra com "Erro de configuração do player". Já está setado nos dois embeds de YouTube (hero da home e player de aula).

**Como o admin usa o Drive** (fluxo manual, sem OAuth — ver seção 8):
1. Sobe o arquivo em drive.google.com
2. Compartilhar → "Qualquer pessoa com o link" → Leitor
3. Configurações avançadas → desativar download/cópia pra quem visualiza
4. Cola o **link inteiro ou só o ID** no campo do painel — o sistema extrai o ID sozinho (`forms_painel.extrair_drive_id`)

---

## 7. Google Drive — por que é manual (não automático)

Foi tentado e **descartado** um fluxo de upload automático direto do painel pro Drive. Histórico, pra não repetir a tentativa:

1. **Conta de serviço (service account)**: não funciona — contas de serviço não têm cota de armazenamento própria em conta Gmail pessoal (só em Google Workspace com "drives compartilhados", que é pago). Erro: `storageQuotaExceeded`.
2. **OAuth com conta pessoal**: chegou a ser implementado por completo (fluxo de conectar/autorizar, guardar refresh_token, criar pasta automática, upload real) — funcionava tecnicamente, mas o usuário decidiu não usar por causa da fricção de configuração (Google Cloud Console, tela de permissão OAuth, usuários de teste, etc) e pediu pra **reverter tudo**. Código foi completamente removido (não existe mais `services_drive.py`, model `GoogleDriveConexao`, views/urls de OAuth).

**Decisão final**: upload manual (admin sobe no Drive, compartilha, cola o ID/link no painel). Simples, sem dependência de credencial nenhuma, funciona hoje.

Se um dia quiser reautomatizar, o caminho certo é OAuth (não conta de serviço) — mas exige o usuário ter conta Google Cloud configurada e aceitar reconectar de vez em quando (token de app em modo "Testing" pode expirar; resolve publicando o app ou verificando com o Google).

---

## 8. Painel administrativo próprio (`/painel/`)

Construído do zero (não é o Django admin) a pedido do cliente, com o visual do próprio site (Tailwind, mesmo header/footer). Só usuários `is_staff` acessam (`@staff_member_required`, reusa login do Django).

**Rotas principais**:
- `/painel/` — dashboard, lista de cursos, botão "Configurações do site" e "+ Novo curso"
- `/painel/configuracoes/` — edita `ConfiguracaoSite` (hero título/subtítulo/vídeo YouTube+Drive, texto do "Sobre", email/telefone/WhatsApp)
- `/painel/cursos/<pk>/` — detalhe do curso: lista módulos+aulas+mentorias, com editar/excluir cada um
- CRUD completo pra Curso, Modulo, Aula, MentoriaAoVivo

**O que NÃO está no painel** (fica só no Django admin, `/admin/`, rebrandado com cores da marca):
- Pagamentos, Matrículas, NotificacaoLog, ContatoMensagem, Certificados, AulaConcluida — são registros/logs de consulta, não precisam de UI custom.

---

## 9. Pagamento mock (arquitetura trocável)

`pagamentos/services.py`: `PaymentGateway` (classe abstrata) → `MockPaymentGateway` (sempre aprova). Factory `get_payment_gateway()` lê `settings.PAYMENT_GATEWAY` (default `"mock"`). Pra integrar Mercado Pago/Stripe de verdade no futuro: implementar uma nova classe com o mesmo contrato (`cobrar(aluno, curso, valor) -> ResultadoPagamento`) e trocar a config — nenhuma view muda.

---

## 10. Notificações mock (arquitetura trocável)

`notificacoes/services.py`: `NotificationBackend` (abstrata) → `MockNotificationBackend` (só grava em `NotificacaoLog` + print no console, não envia nada de verdade). `NotificationService` tem métodos de alto nível: `notificar_matricula`, `notificar_credenciais`, `notificar_contato`. Pra ligar email de verdade: trocar `NOTIFICATION_BACKEND` no `.env` e implementar um backend real (ex: SMTP/SendGrid) com o mesmo contrato.

---

## 11. Progresso e certificado

`matriculas/progresso.py`:
- `calcular_progresso(aluno, curso)` → `{concluidas, total, percentual, completo}`
- `emitir_certificado_se_completo(aluno, curso)` → cria `Certificado` automaticamente quando `concluidas >= total`

Aluno marca aula concluída em `/aulas/<id>/concluir/` (POST). Barra de progresso aparece em "Minha área" e na página de conteúdo do curso. Certificado tem código único (UUID) e página imprimível (`/cursos/<slug>/certificado/`, botão "Imprimir/Salvar PDF", header/footer somem no print via `print:hidden`).

---

## 12. Banco de dados — Supabase

`DATABASE_URL` no `.env` aponta pro Supabase (pooler, porta 6543, `sslmode=require`). Driver: `psycopg2-binary`. Pra voltar a rodar local com SQLite, basta comentar/remover a linha `DATABASE_URL` do `.env`.

⚠️ **A senha do banco está em texto puro no `.env`** (arquivo git-ignorado, nunca commitado — confirmar sempre com `git check-ignore .env` antes de qualquer commit).

---

## 13. Variáveis de ambiente (`.env`)

```
SECRET_KEY=              # chave Django, obrigatória
DEBUG=True/False
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=            # Supabase Postgres (se ausente, cai pra SQLite local)
PAYMENT_GATEWAY=mock     # default, trocar quando integrar gateway real
NOTIFICATION_BACKEND=mock
ADMIN_NOTIFICATION_EMAIL=admin@saulocurso.local
```

---

## 14. Como rodar

**Local (venv)**:
```
./.venv/Scripts/python manage.py migrate
./.venv/Scripts/python manage.py seed_demo_data   # popula 3 cursos de exemplo
./.venv/Scripts/python manage.py runserver 127.0.0.1:8000
```

**Docker**:
```
docker compose up
```

**Credenciais de teste** (criadas pelo `seed_demo_data` / `createsuperuser`):
- Admin: `admin` / `admin12345` — `/admin/` e `/painel/`
- Aluno demo: `aluno.demo` / `demo12345` — já matriculado em "Python do Zero ao Avançado"

---

## 15. Pendências conhecidas / próximos passos

- **Deploy no Vercel: ainda NÃO funciona.** Faltam:
  - Mover `imagem_capa` (foto de capa dos cursos) e PDFs locais pra storage externo (Supabase Storage ou Drive) — Vercel não tem disco persistente
  - Configurar WhiteNoise (ou equivalente) pra servir estáticos
  - Criar `vercel.json` + adaptador WSGI/entrypoint
- **Email/WhatsApp reais**: hoje 100% mock. Pra produção de verdade, trocar `NOTIFICATION_BACKEND` e implementar SMTP real (Gmail/SendGrid) e WhatsApp Business API/Z-API.
- **Gateway de pagamento real**: hoje mock. Trocar por Mercado Pago/Stripe seguindo o contrato de `PaymentGateway`.
- **Tailwind via CDN**: bom pra prototipar, mas não é ideal pra produção (sem purge de CSS). Migrar pra `django-tailwind` com build quando o design estabilizar.
- **Verificação do app OAuth do Google**: não se aplica mais — a integração OAuth foi removida (ver seção 7).

---

## 16. Decisões de design que vale lembrar (pra não repetir debate)

- **Pagamento inteiro mockado de propósito** — cliente aprovou, prioridade era mostrar o fluxo completo, não processar dinheiro de verdade ainda.
- **Cadastro acontece DEPOIS do pagamento**, não antes (mudança de design a pedido do cliente — versão antiga era "cadastro → paga", foi invertida).
- **Preço só aparece no checkout**, nunca na página pública do curso.
- **CSS framework**: Tailwind (não Bootstrap) — escolha explícita do cliente.
- **Painel custom > Django admin rebrandado**: cliente pediu especificamente uma tela própria pro dia a dia (cursos/módulos/aulas), mas preferiu manter o Django admin pronto pra tudo que é só log/consulta (não vale reconstruir o que o Django já resolve de graça).
- **Vídeo protegido é deterrente, não DRM** — indústria não tem solução 100% client-side contra usuário técnico; o cliente foi informado e aceitou esse trade-off desde o início.

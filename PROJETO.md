# RS Central dos Cursos — Documentação do Projeto

Plataforma de venda e entrega de cursos online. Django + Tailwind (CDN) + Supabase (Postgres). Deploy na Vercel.
Este documento existe pra qualquer pessoa (ou IA) entender o projeto do zero, sem precisar reler a conversa inteira que o gerou.

> **Nota histórica**: este projeto nasceu como protótipo genérico ("Saulo Curso", branding placeholder) e foi
> rebrandado no mesmo repositório/banco pro cliente real **RS Central dos Cursos** (cursos de saúde/emergência:
> APH, BLS, Stop The Bleed, Lei Lucas, etc). A arquitetura genérica (matrícula, pagamento, painel, certificado)
> não mudou — só a marca, paleta de cores e os campos de conteúdo que o novo briefing exigiu.

---

## 1. Visão geral

- Cliente compra curso → paga (mock) → cadastra (nome/CPF/telefone/email) → recebe senha temporária por email (mock) → troca senha no primeiro acesso → acessa aulas (vídeo + PDF) → marca aulas concluídas → ganha certificado ao completar 100%.
- Admin cadastra cursos/módulos/aulas/mentorias/turmas/FAQ por um **painel próprio** (não é o Django admin) e edita textos da home + dados institucionais por uma tela de **Configurações do site**.
- Vídeos vêm do **YouTube** ou **Google Drive** (ID ou link colado manualmente, extraído sozinho); PDFs e capa de curso só por **Google Drive** ou **link externo** — **não existe mais upload local de arquivo** (removido de propósito, ver seção 17, por causa do deploy na Vercel não ter disco persistente).

---

## 2. Stack

- Django 6.0 (Python 3.13), function-based views em quase tudo
- Tailwind CSS via **CDN** (Play CDN) — sem build step, prototípico de propósito
- Banco: **Supabase Postgres** (produção/atual) — local cai pra SQLite se `DATABASE_URL` não estiver setado
- `django-environ` pra config via `.env`
- Sem REST framework, sem JS framework — só fetch() + DOM puro nos pontos que precisam (player de vídeo/pdf, toggle de tema)
- Deploy: **Vercel** (`vercel.json` + `api/index.py` como entrypoint WSGI) — ver seção 13

---

## 3. Apps Django

| App | Responsabilidade |
|---|---|
| `config` | settings, urls raiz |
| `accounts` | `Perfil` (extra do User), login, troca de senha obrigatória, middleware |
| `cursos` | Curso, Módulo, Aula, MentoriaAoVivo, Turma, PerguntaFrequente, ConfiguracaoSite, ContatoMensagem — views públicas + **painel próprio** (`views_painel.py`, `urls_painel.py`, `forms_painel.py`) |
| `matriculas` | Matricula (aluno×curso), AulaConcluida, Certificado, lógica de progresso e controle de acesso (`mixins.py`) |
| `pagamentos` | Pagamento, gateway mock trocável, fluxo de checkout + cadastro pós-pagamento |
| `notificacoes` | NotificacaoLog, serviço de notificação mock (email/whatsapp) trocável |

---

## 4. Modelos principais

**cursos.Curso** — titulo, slug, descricao_curta, descricao, preco, carga_horaria (texto livre), modalidade
(choices: presencial/online/híbrido), drive_capa_file_id, capa_url_externa (link direto, prioridade pro Drive
se os dois preenchidos), video_youtube_id, ativo. Property `capa_url` resolve a fonte certa; `icone_tematico`
devolve um emoji por palavra-chave do título (fallback visual quando não tem capa).
**cursos.Modulo** — curso FK, titulo, ordem
**cursos.Aula** — modulo FK, titulo, youtube_id, drive_file_id, drive_pdf_file_id, ordem (sem upload local)
**cursos.MentoriaAoVivo** — curso FK, titulo, descricao, data_hora, link_reuniao — sessão ao vivo **privada**,
só pra aluno matriculado (aparece dentro do conteúdo do curso)
**cursos.Turma** — curso FK, data_inicio, local_ou_modalidade, vagas, observacao — data de início **pública**,
alimenta a página `/agenda/` (conceito distinto de `MentoriaAoVivo`: essa é institucional/marketing, não some
atrás de login)
**cursos.PerguntaFrequente** — pergunta, resposta, ordem, ativa — alimenta a seção FAQ da home
**cursos.ConfiguracaoSite** — singleton (pk=1 via `.obter()`), textos do hero/sobre/contato da home + cnpj,
endereco, instagram_url (dados institucionais do rodapé)
**cursos.ContatoMensagem** — tipo (contato geral / orçamento-empresas), email, telefone, mensagem — mesmo
model atende `/contato/` e `/empresas/`, diferenciado só pelo campo `tipo`

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

**Arquitetura**: o ID do vídeo/pdf **nunca aparece no HTML inicial**. A página `/aulas/<id>/` carrega um player vazio; JS busca `/aulas/<id>/video-token/` (e `/pdf-token/`), endpoint protegido por `matricula_required_aula` (só responde se o usuário tem matrícula ativa no curso daquela aula), que devolve `{"fonte": "youtube"|"drive", ...}`. O JS monta o iframe em runtime.

**Fontes possíveis por aula** (prioridade: Drive > YouTube pra vídeo; PDF só existe via Drive):
- `youtube_id` — embed `youtube.com/embed/ID` com `rel=0&modestbranding=1&fs=0&disablekb=1&iv_load_policy=3`. Tem **overlay invisível** (topo 24% + canto inferior-direito) que bloqueia clique no título/badge "Assista no YouTube" — só enquanto o vídeo NÃO está tocando (usa a IFrame API do YouTube pra saber o estado e sumir com o bloqueio durante a reprodução real, senão cobriria os controles).
- `drive_file_id` / `drive_pdf_file_id` — embed `drive.google.com/file/d/ID/preview`. Mesmo overlay (56×56px) no canto superior-direito bloqueando o ícone "abrir em outra janela" do Drive.

**Upload local de PDF foi removido** (campo `arquivo_pdf` existiu, foi tirado do model) — Vercel não tem disco
persistente, então só Drive faz sentido em produção. Ver seção 17.

**Botão de tela cheia próprio** — tanto o player de vídeo (`#fullscreen-btn`) quanto o de PDF
(`#pdf-fullscreen-btn`) usam a Fullscreen API do navegador no `<div>` que envolve o iframe, não no iframe em
si. Existe porque o YouTube tem `fs=0` (desativado de propósito) e porque o overlay que bloqueia download no
Drive também cobriria o ícone de tela cheia nativo do Drive se não tivesse um botão próprio por cima.

**Importante — YouTube error 153**: desde ~final de 2025 o YouTube exige `referrerpolicy="strict-origin-when-cross-origin"` no iframe, senão o embed quebra com "Erro de configuração do player". Já está setado nos dois embeds de YouTube (hero da home e player de aula).

**Como o admin usa o Drive** (fluxo manual, sem OAuth — ver seção 8):
1. Sobe o arquivo em drive.google.com
2. Compartilhar → "Qualquer pessoa com o link" → Leitor
3. Configurações avançadas → desativar download/cópia pra quem visualiza
4. Cola o **link inteiro ou só o ID** no campo do painel — o sistema extrai o ID sozinho (`forms_painel.extrair_drive_id`, e `extrair_youtube_id` pro campo de vídeo)

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
- `/painel/` — dashboard, lista de cursos, botões "Perguntas frequentes", "Configurações do site" e "+ Novo curso"
- `/painel/configuracoes/` — edita `ConfiguracaoSite` (hero, "Sobre", contato, **cnpj/endereço/Instagram**)
- `/painel/cursos/<pk>/` — detalhe do curso: lista módulos+aulas, mentorias **e turmas**, com editar/excluir cada um
- `/painel/faq/` — lista/cria/edita/exclui `PerguntaFrequente` (única lista "solta", sem curso pai)
- CRUD completo pra Curso, Modulo, Aula, MentoriaAoVivo, Turma, PerguntaFrequente

**O que NÃO está no painel** (fica só no Django admin, `/admin/`, rebrandado com cores da marca):
- Pagamentos, Matrículas, NotificacaoLog, ContatoMensagem, Certificados, AulaConcluida — são registros/logs de consulta, não precisam de UI custom.

---

## 9. Páginas públicas (nav/rodapé) e identidade visual

**Rotas públicas institucionais** (além de home/cursos/matrícula):
- `/agenda/` — lista `Turma` futura (`data_inicio__gte=now`), ordenada por data; estado vazio tratado
- `/empresas/` — página de treinamentos in company, com os diferenciais reais do material do cliente + formulário de orçamento (`ContatoMensagem` com `tipo=empresa`)
- `/certificados/` — busca de certificado por código (redireciona pra `/certificados/<uuid>/verificar/`); a rota com UUID direto só é alcançável por quem já tem o código (ex: QR Code escaneado)
- `/privacidade/` — texto estático placeholder, **precisa ser substituído pelo texto jurídico real** do cliente

**Identidade visual** (a partir de material de referência que o cliente mandou — posts de Instagram, pasta `ideias/`):
- Paleta: vermelho/laranja/dourado ("fogo") — cor de marca (`brand`) é vermelho (`#dc2626`/`#991b1b`); gradiente
  laranja→dourado vira o utilitário `.bg-ember`/`.text-ember` (botões, títulos de destaque, badges)
- Hero, seção "in company", CTA final e o strip por trás dos cards de curso usam fundo escuro/preto com o
  gradiente de fogo — resto do site fica claro, pra não ficar "extravagante" (pedido explícito do cliente)
- **Dark mode manual**: botão de sol/lua na nav (`#theme-toggle`), classe `dark` no `<html>`, persiste em
  `localStorage`. Tailwind configurado com `darkMode: 'class'`. Cobertura completa em `base.html` e `home.html`;
  páginas secundárias (contato/agenda/empresas) têm cobertura parcial — cards continuam claros mesmo com o
  tema escuro ativo (efeito "cartão claro sobre fundo escuro", não é bug).
- Logo do cliente em `static/img/logo.jpg` (fundo preto sólido, não é PNG transparente) — por isso só é usada
  sobre fundos escuros (nav/rodapé) sem problema visual.
- `Curso.icone_tematico` dá um emoji por palavra-chave do título quando não tem capa (cruz médica, coração,
  etc) — fallback melhor que texto puro, não substitui foto real.

---

## 10. Pagamento mock (arquitetura trocável)

`pagamentos/services.py`: `PaymentGateway` (classe abstrata) → `MockPaymentGateway` (sempre aprova). Factory `get_payment_gateway()` lê `settings.PAYMENT_GATEWAY` (default `"mock"`). Pra integrar Mercado Pago/Stripe de verdade no futuro: implementar uma nova classe com o mesmo contrato (`cobrar(aluno, curso, valor) -> ResultadoPagamento`) e trocar a config — nenhuma view muda.

---

## 11. Notificações mock (arquitetura trocável)

`notificacoes/services.py`: `NotificationBackend` (abstrata) → `MockNotificationBackend` (só grava em `NotificacaoLog` + print no console, não envia nada de verdade). `NotificationService` tem métodos de alto nível: `notificar_matricula`, `notificar_credenciais`, `notificar_contato` (assunto varia se é contato geral ou orçamento de empresa, via `ContatoMensagem.tipo`). Pra ligar email de verdade: trocar `NOTIFICATION_BACKEND` no `.env` e implementar um backend real (ex: SMTP/SendGrid) com o mesmo contrato.

---

## 12. Progresso e certificado

`matriculas/progresso.py`:
- `calcular_progresso(aluno, curso)` → `{concluidas, total, percentual, completo}`
- `emitir_certificado_se_completo(aluno, curso)` → cria `Certificado` automaticamente quando `concluidas >= total`

Aluno marca aula concluída em `/aulas/<id>/concluir/` (POST). Barra de progresso aparece em "Minha área" e na página de conteúdo do curso. Certificado tem código único (UUID), QR Code (`/certificados/<uuid>/qrcode/`) e página imprimível (`/cursos/<slug>/certificado/`, botão "Imprimir/Salvar PDF", header/footer somem no print via `print:hidden`). Busca por código em `/certificados/`.

---

## 13. Deploy — Vercel

Funciona (feito nesta rebrand — antes não funcionava, ver seção 17 pra histórico).

- `vercel.json` — builds `api/index.py` (`@vercel/python`) + serve `static/**` direto (`@vercel/static`); todas as outras rotas caem no WSGI
- `api/index.py` — entrypoint: seta `DJANGO_SETTINGS_MODULE`, importa `config.wsgi.application`
- Estáticos do Django admin (CSS/JS) foram **coletados manualmente uma vez** (`collectstatic` local) e commitados em `static/admin/` — Vercel não roda `collectstatic` no build, então isso é necessário sempre que o Django for atualizado de versão (senão a tela de admin/login fica sem estilo)
- `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` sempre incluem `.vercel.app` no código (não dependem só de env var, pra não quebrar se a env var no dashboard for setada sem esse domínio)
- Variáveis de ambiente reais (`SECRET_KEY`, `DEBUG=False`, `DATABASE_URL`) ficam no dashboard da Vercel, não no `.env` local

---

## 14. Banco de dados — Supabase

`DATABASE_URL` no `.env` aponta pro Supabase (pooler, porta 6543, `sslmode=require`). Driver: `psycopg2-binary`. Pra voltar a rodar local com SQLite, basta comentar/remover a linha `DATABASE_URL` do `.env`.

⚠️ **A senha do banco está em texto puro no `.env`** (arquivo git-ignorado, nunca commitado — confirmar sempre com `git check-ignore .env` antes de qualquer commit).

---

## 15. Variáveis de ambiente (`.env`)

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

## 16. Como rodar

**Local (venv)**:
```
./.venv/Scripts/python manage.py migrate
./.venv/Scripts/python manage.py seed_demo_data   # popula cursos de exemplo genéricos (não é conteúdo real do cliente)
./.venv/Scripts/python manage.py runserver 127.0.0.1:8000
```

**Docker**:
```
docker compose up
```

**Credenciais de teste** (criadas pelo `seed_demo_data` / `createsuperuser`):
- Admin: `admin` / `admin12345` — `/admin/` e `/painel/`
- Aluno demo: `aluno.demo` / `demo12345`

---

## 17. Pendências conhecidas / próximos passos

**Conteúdo real do cliente** (não é trabalho de código, é preenchimento — tudo já tem campo/UI pronto no painel):
- Preço real dos 8 cursos (hoje **R$ 297,00 placeholder** em todos, exceto o que for ajustado)
- Carga horária/modalidade reais por curso (hoje "30 horas"/Online default em quase todos — BLS já tem 8h real)
- Fotos reais de capa dos cursos (hoje usa ícone temático de fallback, `Curso.icone_tematico`)
- CNPJ, endereço, Instagram, e-mail de contato oficial (hoje `contato@saulocurso.local`, resquício do protótipo)
- Texto real da Política de Privacidade (`/privacidade/` tem só placeholder)
- Turmas reais (datas) pra `/agenda/` não ficar vazia
- Logo com fundo transparente, se quiser usar em algum lugar de fundo claro (hoje só aparece bem sobre fundo escuro)

**Técnico**:
- **Email/WhatsApp reais**: hoje 100% mock. Pra produção de verdade, trocar `NOTIFICATION_BACKEND` e implementar SMTP real (Gmail/SendGrid) e WhatsApp Business API/Z-API.
- **Gateway de pagamento real**: hoje mock. Trocar por Mercado Pago/Stripe seguindo o contrato de `PaymentGateway`.
- **Tailwind via CDN**: bom pra prototipar, mas não é ideal pra produção (sem purge de CSS). Migrar pra `django-tailwind` com build quando o design estabilizar.
- **Verificação do app OAuth do Google**: não se aplica — a integração OAuth foi removida (ver seção 7).
- **Dark mode**: cobertura completa só em `base.html`/`home.html`; se quiser 100% das páginas com tema escuro fiel, falta passar pelas páginas secundárias (contato, agenda, empresas, painel, certificado).

---

## 18. Decisões de design que vale lembrar (pra não repetir debate)

- **Pagamento inteiro mockado de propósito** — cliente aprovou, prioridade era mostrar o fluxo completo, não processar dinheiro de verdade ainda.
- **Cadastro acontece DEPOIS do pagamento**, não antes (mudança de design a pedido do cliente — versão antiga era "cadastro → paga", foi invertida).
- **Preço só aparece no checkout**, nunca na página pública do curso.
- **CSS framework**: Tailwind (não Bootstrap) — escolha explícita do cliente.
- **Painel custom > Django admin rebrandado**: cliente pediu especificamente uma tela própria pro dia a dia (cursos/módulos/aulas), mas preferiu manter o Django admin pronto pra tudo que é só log/consulta (não vale reconstruir o que o Django já resolve de graça).
- **Vídeo protegido é deterrente, não DRM** — indústria não tem solução 100% client-side contra usuário técnico; o cliente foi informado e aceitou esse trade-off desde o início.
- **Rebrand no mesmo repo/banco, não projeto novo** — decisão explícita do usuário: reaproveitar toda a arquitetura genérica em vez de criar um projeto separado pro cliente real.
- **Upload local removido (imagem de capa e PDF de apostila)** — a pedido explícito do usuário, depois do deploy Vercel expor que fs local não persiste; ficou só Drive/link externo/YouTube.
- **Diferenciais e público-alvo da home são hardcoded no template, não modelo/CRUD** — conteúdo institucional que não muda com frequência; segue o mesmo padrão da seção "sobre" original. FAQ, por outro lado, virou model com CRUD porque é conteúdo que cresce/muda.
- **`Turma` é um model novo, separado de `MentoriaAoVivo`** — mentoria é sessão ao vivo privada pós-matrícula; turma é data de início pública, pensada pra página de Agenda no menu principal.
- **Paleta de cores veio de material de referência do próprio cliente** (posts prontos de Instagram), não escolha livre — "mesma paleta, nada extravagante" foi a instrução literal.

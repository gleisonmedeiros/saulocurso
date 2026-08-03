RS CENTRAL DOS CURSOS — INSTALAÇÃO
====================================

Script: install.py. Roda no Windows (teste) e Ubuntu (VPS). Banco:
PostgreSQL (SQLite trava em escrita concorrente, só serve pra teste).


TESTE LOCAL (Windows)
----------------------
    python install.py setup --sqlite
    python install.py superusuario
    python install.py rodar    -> http://127.0.0.1:8000/

No Windows: sempre "rodar", nunca "servir"/"servico" (gunicorn é Unix-only).


VPS (Ubuntu 22.04/24.04, 1 vCPU / 4 GB)
------------------------------------------
5 passos, nessa ordem, um de cada vez (sem "tudo" ainda — não testado
em VPS real):

1) sudo python3 install.py sistema
   apt: postgres, nginx, build tools. Avisa se falta swap.

2) python3 install.py banco --db-pass 'SENHA_FORTE'
   Cria role+database Postgres local, grava DATABASE_URL no .env.

3) python3 install.py setup --domain seudominio.com.br
   venv + deps + .env + migrate + collectstatic.
   Se SUPABASE_DATABASE_URL já estiver gravada no .env (ou passar
   --importar-de "postgresql://...url..."), e o banco local estiver
   vazio (1ª instalação), o setup PERGUNTA sozinho:
       "Importar os dados do Supabase agora? [s/N]"
   Responde "s" pra puxar tudo (cursos, users, matrículas...) na hora.
   Se já tiver dado no banco local, pula direto sem perguntar.

4) python3 install.py superusuario
   Cria login admin (/admin/ e /painel/).

5) sudo python3 install.py servico --domain seudominio.com.br
   systemd (gunicorn) + nginx. Site no ar.

HTTPS (DNS já apontado pro IP antes):
    sudo apt install -y certbot python3-certbot-nginx
    sudo certbot --nginx -d seudominio.com.br -d www.seudominio.com.br


IMPORTAR DADOS DO SUPABASE MANUALMENTE
------------------------------------------
Copia os dados (cursos, módulos, aulas, users, matrículas, pagamentos)
do Supabase pro banco local atual (o que estiver em DATABASE_URL do
.env). Não escreve nada no Supabase (só leitura).

    python install.py importar-supabase --source "postgresql://...url..."

Ou grava a URL uma vez no .env (chave SUPABASE_DATABASE_URL) e roda só:

    python install.py importar-supabase

Trava de segurança: se DATABASE_URL local == origem, recusa (evitaria
importar o banco em cima dele mesmo). Configure o banco local primeiro
(SQLite ou "install.py banco") antes de importar.


DEPOIS DE INSTALADO
---------------------
python3 install.py atualizar   -> git pull + deps + migrate + restart
python3 install.py backup      -> dump em backups/saulocurso.sql
python install.py checar       -> diagnóstico
python install.py --help       -> todos comandos


ATENÇÃO
---------
- sudo pode pedir senha — rodar interativo, não script.
- Certbot exige DNS já apontado; sem isso só essa etapa falha.
- "sistema"/"banco"/"servico" ainda não testados em VPS Ubuntu real
  (só revisão de código) — ajustar se travar na primeira vez.


GERADOS (gitignored)
-----------------------
.venv/, .env, db.sqlite3, _staticfiles_build/, deploy/, backups/

#!/usr/bin/env python3
"""
Instalador / operador do RS Central dos Cursos.

Roda em Windows (teste local) e Ubuntu (VPS Hostinger). Só stdlib — pode ser
executado com o Python do sistema, antes de existir qualquer venv.

Uso rápido na VPS (Ubuntu 22.04/24.04, 1 vCPU / 4 GB):

    sudo python3 install.py sistema
    python3 install.py banco --db-pass 'SENHA_FORTE'
    python3 install.py setup --domain meudominio.com.br
    python3 install.py superusuario
    sudo python3 install.py servico --domain meudominio.com.br

Uso local (Windows, teste):

    python install.py setup --sqlite
    python install.py superusuario
    python install.py rodar

(No Windows use sempre "rodar", não "servir"/"servico" — gunicorn precisa de
fcntl e só roda em Linux/Mac. "servir"/"servico" são pra a VPS Ubuntu.)

Cada comando é idempotente: pode rodar de novo sem quebrar nada.
"""

from __future__ import annotations

import argparse
import os
import platform
import secrets
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

# Windows usa cp1252 como encoding padrão de arquivo/subprocesso, o que
# quebra dumpdata/loaddata em textos com acento (Django sempre lê/escreve
# JSON como UTF-8). Força UTF-8 em todo processo filho (manage.py etc).
os.environ.setdefault("PYTHONUTF8", "1")

BASE_DIR = Path(__file__).resolve().parent
VENV_DIR = BASE_DIR / ".venv"
ENV_FILE = BASE_DIR / ".env"
DEPLOY_DIR = BASE_DIR / "deploy"
STATIC_ROOT = BASE_DIR / "_staticfiles_build"

IS_WINDOWS = os.name == "nt"
PY_MIN = (3, 12)

# Nome do projeto/serviço/usuário do sistema na VPS.
APP_NAME = "saulocurso"

# 1 vCPU / 4 GB: workers sync puros desperdiçam CPU em I/O (Supabase/Postgres
# remoto, chamadas externas). gthread com 2 workers x 4 threads segura bem e
# fica em ~250 MB de RAM.
GUNICORN_WORKERS = 2
GUNICORN_THREADS = 4

PACOTES_APT = [
    "python3",
    "python3-venv",
    "python3-dev",
    "build-essential",
    "libpq-dev",
    "libjpeg-dev",
    "zlib1g-dev",
    "postgresql",
    "postgresql-contrib",
    "nginx",
    "git",
    "curl",
]


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #

# Cor só em terminal de verdade — em log/pipe o escape vira lixo no arquivo.
COR = sys.stdout.isatty() and os.environ.get("TERM") != "dumb"


def _c(codigo: str, texto: str) -> str:
    return f"\033[{codigo}m{texto}\033[0m" if COR else texto


def log(msg: str) -> None:
    print(f"\n{_c('1;36', '==>')} {msg}")


def ok(msg: str) -> None:
    print(f"    {_c('1;32', 'ok')}  {msg}")


def aviso(msg: str) -> None:
    print(f"    {_c('1;33', '!!')}  {msg}")


def erro(msg: str, codigo: int = 1) -> None:
    print(f"\n{_c('1;31', 'ERRO:')} {msg}\n", file=sys.stderr)
    sys.exit(codigo)


def run(cmd: list[str], check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    print(f"    $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run([str(c) for c in cmd], check=check, **kwargs)


def venv_python() -> Path:
    return VENV_DIR / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")


def venv_bin(nome: str) -> Path:
    sufixo = ".exe" if IS_WINDOWS else ""
    return VENV_DIR / ("Scripts" if IS_WINDOWS else "bin") / f"{nome}{sufixo}"


def exigir_venv() -> Path:
    py = venv_python()
    if not py.exists():
        erro(f"venv não encontrado em {VENV_DIR}. Rode primeiro: python install.py setup")
    return py


def manage(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return run([exigir_venv(), BASE_DIR / "manage.py", *args], check=check)


def is_root() -> bool:
    return not IS_WINDOWS and os.geteuid() == 0


def eh_ubuntu() -> bool:
    return platform.system() == "Linux"


def ler_env() -> dict[str, str]:
    """Lê o .env atual (formato CHAVE=valor, sem interpolação)."""
    dados: dict[str, str] = {}
    if not ENV_FILE.exists():
        return dados
    for linha in ENV_FILE.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        dados[chave.strip()] = valor.strip()
    return dados


def escrever_env(dados: dict[str, str]) -> None:
    ordem = [
        "SECRET_KEY", "DEBUG", "ALLOWED_HOSTS", "CSRF_TRUSTED_ORIGINS",
        "DATABASE_URL",
        "ADMIN_NOTIFICATION_EMAIL",
        # Não lida pelo Django/settings.py — só usada pelo comando
        # "importar-supabase" deste script, como origem dos dados.
        "SUPABASE_DATABASE_URL",
    ]
    linhas = ["# Gerado por install.py — NÃO commitar este arquivo.", ""]
    for chave in ordem:
        if chave in dados:
            linhas.append(f"{chave}={dados[chave]}")
    for chave, valor in dados.items():
        if chave not in ordem:
            linhas.append(f"{chave}={valor}")
    ENV_FILE.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    if not IS_WINDOWS:
        ENV_FILE.chmod(0o600)  # contém senha do banco


# --------------------------------------------------------------------------- #
# Comandos
# --------------------------------------------------------------------------- #

def cmd_checar(args: argparse.Namespace) -> None:
    log("Checando ambiente")
    print(f"    Python.......: {sys.version.split()[0]} ({sys.executable})")
    print(f"    SO...........: {platform.system()} {platform.release()}")
    print(f"    Projeto......: {BASE_DIR}")

    if sys.version_info < PY_MIN:
        erro(f"Python {PY_MIN[0]}.{PY_MIN[1]}+ é obrigatório (Django 6.0).")
    ok("versão do Python compatível")

    print(f"    venv.........: {'existe' if venv_python().exists() else 'ausente'}")
    print(f"    .env.........: {'existe' if ENV_FILE.exists() else 'ausente'}")

    for exe in ("psql", "nginx", "systemctl"):
        caminho = shutil.which(exe)
        print(f"    {exe:<12.12}: {caminho or 'não encontrado'}")

    if venv_python().exists():
        run([venv_python(), "-c", "import django; print('    Django.......:', django.get_version())"], check=False)


def cmd_sistema(args: argparse.Namespace) -> None:
    """Instala pacotes de sistema (só Ubuntu, precisa de sudo)."""
    if not eh_ubuntu():
        aviso("Comando 'sistema' só faz sentido no Ubuntu. Pulando.")
        return
    if not is_root():
        erro("Precisa de root. Rode: sudo python3 install.py sistema")

    log("Instalando pacotes do sistema (apt)")
    run(["apt-get", "update"])
    run(["apt-get", "install", "-y", "--no-install-recommends", *PACOTES_APT])
    ok("pacotes instalados")

    log("Habilitando PostgreSQL e Nginx no boot")
    run(["systemctl", "enable", "--now", "postgresql"], check=False)
    run(["systemctl", "enable", "--now", "nginx"], check=False)

    log("Checando swap (VPS de 4 GB com 1 núcleo se beneficia de 2 GB de swap)")
    resultado = run(["swapon", "--show"], check=False, capture_output=True, text=True)
    if resultado.stdout.strip():
        ok("swap já configurado")
    else:
        aviso("Sem swap. Para criar 2 GB:")
        print("      fallocate -l 2G /swapfile && chmod 600 /swapfile")
        print("      mkswap /swapfile && swapon /swapfile")
        print("      echo '/swapfile none swap sw 0 0' >> /etc/fstab")


def cmd_banco(args: argparse.Namespace) -> None:
    """Cria role + database no Postgres local e grava DATABASE_URL no .env."""
    if not shutil.which("psql"):
        erro("psql não encontrado. Rode antes: sudo python3 install.py sistema")

    nome = args.db_name
    usuario = args.db_user
    senha = args.db_pass or secrets.token_urlsafe(24)

    if "'" in senha or '"' in senha or "\\" in senha:
        erro("A senha do banco não pode conter aspas nem barra invertida (quebra o SQL e a URL).")

    log(f"Criando role '{usuario}' e database '{nome}' no PostgreSQL local")

    def psql(sql: str, db: str = "postgres") -> subprocess.CompletedProcess:
        """Executa SQL como o usuário 'postgres' (dono do cluster)."""
        cmd = ["psql", "-d", db, "-v", "ON_ERROR_STOP=1", "-c", sql]
        if is_root():
            cmd = ["runuser", "-u", "postgres", "--", *cmd]
        elif shutil.which("sudo"):
            cmd = ["sudo", "-u", "postgres", *cmd]
        return run(cmd, check=False, capture_output=True, text=True)

    # Role (idempotente).
    r = psql(f"CREATE ROLE {usuario} LOGIN PASSWORD '{senha}';")
    if r.returncode != 0 and "already exists" in (r.stderr or ""):
        aviso(f"role '{usuario}' já existe — atualizando a senha")
        r = psql(f"ALTER ROLE {usuario} WITH LOGIN PASSWORD '{senha}';")
    if r.returncode != 0:
        erro(f"falha criando/atualizando role:\n{r.stderr}")
    ok(f"role '{usuario}' pronta")

    # Database (idempotente).
    r = psql(f"CREATE DATABASE {nome} OWNER {usuario} ENCODING 'UTF8';")
    if r.returncode != 0 and "already exists" in (r.stderr or ""):
        aviso(f"database '{nome}' já existe — mantendo")
    elif r.returncode != 0:
        erro(f"falha criando database:\n{r.stderr}")
    else:
        ok(f"database '{nome}' criado")

    # Django precisa criar tabelas; no PG 15+ o schema public não é mais
    # gravável por padrão, então o GRANT abaixo é obrigatório.
    psql(f"GRANT ALL PRIVILEGES ON DATABASE {nome} TO {usuario};")
    psql(f"GRANT ALL ON SCHEMA public TO {usuario};", db=nome)
    psql(f"ALTER SCHEMA public OWNER TO {usuario};", db=nome)

    url = f"postgres://{usuario}:{quote(senha, safe='')}@127.0.0.1:5432/{nome}"
    dados = ler_env()
    dados["DATABASE_URL"] = url
    if "SECRET_KEY" not in dados:
        dados["SECRET_KEY"] = secrets.token_urlsafe(50)
    escrever_env(dados)

    ok("DATABASE_URL gravada no .env")
    print(f"\n    Senha do banco: {senha}")
    print("    Guarde essa senha — ela também está no .env (chmod 600).")


def cmd_setup(args: argparse.Namespace) -> None:
    """venv + dependências + .env + migrate + collectstatic."""
    cmd_checar(args)

    log("Criando/validando venv")
    if venv_python().exists():
        ok(f"venv já existe em {VENV_DIR}")
    else:
        run([sys.executable, "-m", "venv", VENV_DIR])
        ok(f"venv criado em {VENV_DIR}")

    py = venv_python()

    log("Atualizando pip e instalando dependências")
    run([py, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
    run([py, "-m", "pip", "install", "--no-cache-dir", "-r", BASE_DIR / "requirements.txt"])
    ok("dependências instaladas")

    log("Configurando .env")
    dados = ler_env()
    criado_agora = not dados

    if "SECRET_KEY" not in dados:
        dados["SECRET_KEY"] = secrets.token_urlsafe(50)
        ok("SECRET_KEY gerada")

    dados["DEBUG"] = "True" if args.debug else "False"

    hosts = ["localhost", "127.0.0.1"]
    origens = []
    if args.domain:
        dominio = args.domain.replace("https://", "").replace("http://", "").strip("/")
        hosts += [dominio, f"www.{dominio}"]
        origens += [f"https://{dominio}", f"https://www.{dominio}"]
    dados["ALLOWED_HOSTS"] = ",".join(dict.fromkeys(hosts))
    if origens:
        dados["CSRF_TRUSTED_ORIGINS"] = ",".join(origens)

    if args.sqlite:
        dados.pop("DATABASE_URL", None)
        aviso("modo SQLite — DATABASE_URL removida do .env (só pra teste local)")
    elif args.database_url:
        dados["DATABASE_URL"] = args.database_url
    elif "DATABASE_URL" not in dados:
        aviso("DATABASE_URL ausente. O Django vai cair pra SQLite.")
        aviso("Pra Postgres: rode 'python3 install.py banco' ou passe --database-url.")

    dados.setdefault("ADMIN_NOTIFICATION_EMAIL", "admin@localhost")
    escrever_env(dados)
    ok(f".env {'criado' if criado_agora else 'atualizado'} ({ENV_FILE})")

    log("Rodando migrations")
    manage("migrate", "--noinput")

    origem_import = args.importar_de or dados.get("SUPABASE_DATABASE_URL")
    if origem_import:
        _perguntar_e_importar_supabase(origem_import)

    log("Coletando arquivos estáticos")
    manage("collectstatic", "--noinput", "--clear")
    ok(f"estáticos em {STATIC_ROOT}")

    log("Checagem de deploy do Django")
    manage("check", "--deploy", check=False)

    print("\n" + "-" * 70)
    print("Setup concluído. Próximos passos:")
    print("  python install.py superusuario     # cria admin do painel")
    print("  python install.py seed             # dados de exemplo (opcional)")
    print("  python install.py rodar            # servidor de desenvolvimento")
    print("  sudo python3 install.py servico --domain SEU.DOMINIO   # produção")
    print("-" * 70)


# Excluídos da exportação: contenttypes/permissions são recriados pelo
# Django a cada migrate (post_migrate signal) e colidem de PK no destino;
# sessions são efêmeras; admin.logentry é histórico, sem valor pra migrar.
DUMPDATA_EXCLUIR = ["contenttypes", "auth.permission", "admin.logentry", "sessions.session"]


def _rodar_com_database_url(url: str, *args: str, **kwargs) -> subprocess.CompletedProcess:
    """Roda manage.py com DATABASE_URL sobrescrita só nesse processo filho
    (não mexe no .env) — usado pra apontar pro banco de ORIGEM (Supabase)
    sem trocar o banco que a aplicação usa no dia a dia."""
    env = os.environ.copy()
    env["DATABASE_URL"] = url
    return run([exigir_venv(), BASE_DIR / "manage.py", *args], env=env, **kwargs)


def cmd_importar_supabase(args: argparse.Namespace) -> None:
    """Copia os dados (fixture JSON) do Supabase pro banco local atual.

    Origem = --source (ou SUPABASE_DATABASE_URL do .env), só leitura.
    Destino = DATABASE_URL atual do .env (o banco que a app usa).
    Nunca escreve na origem — dumpdata é leitura pura.
    """
    dados = ler_env()
    origem = args.source or dados.get("SUPABASE_DATABASE_URL")
    if not origem:
        erro("Sem banco de origem. Use --source 'postgres://...' ou grave SUPABASE_DATABASE_URL no .env.")

    destino = dados.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
    if destino.strip() == origem.strip():
        erro(
            "DATABASE_URL local está igual à origem Supabase — isso importaria o banco em cima "
            "dele mesmo. Configure o banco local primeiro (python install.py banco) antes de importar."
        )

    log("Preparando banco local (migrate) antes de importar")
    manage("migrate", "--noinput")

    dump_path = BASE_DIR / "_import_supabase.json"
    log("Exportando dados do Supabase (só leitura, nada é alterado lá)")
    excluir_flags = [flag for app in DUMPDATA_EXCLUIR for flag in ("-e", app)]
    _rodar_com_database_url(origem, "dumpdata", *excluir_flags, "-o", str(dump_path))
    tamanho_kb = dump_path.stat().st_size // 1024
    ok(f"dump salvo: {dump_path} ({tamanho_kb} KB)")

    log("Importando dados no banco local")
    manage("loaddata", str(dump_path))
    ok("dados importados no banco local")

    dump_path.unlink(missing_ok=True)
    ok("arquivo temporário removido (continha dados de usuários — CPF, telefone, senha com hash)")


def _contar_cursos_locais() -> int | None:
    """None quando não deu pra checar (banco inacessível etc) — trata como
    'não arrisca' em vez de assumir vazio."""
    py = exigir_venv()
    resultado = run(
        [py, "manage.py", "shell", "-c", "from cursos.models import Curso; print(Curso.objects.count())"],
        capture_output=True, text=True, check=False,
    )
    try:
        return int(resultado.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return None


def _perguntar_e_importar_supabase(origem: str) -> None:
    """Chamado pelo 'setup' quando há uma origem Supabase configurada
    (--importar-de ou SUPABASE_DATABASE_URL no .env). Só oferece a
    importação se o banco local estiver vazio — evita reimportar (e
    duplicar) em toda atualização/reinstalação."""
    contagem = _contar_cursos_locais()

    if contagem is None:
        aviso("não consegui checar se o banco local já tem dados — pulando importação por segurança.")
        aviso("Rode manualmente depois: python install.py importar-supabase")
        return

    if contagem > 0:
        aviso(f"banco local já tem {contagem} curso(s) cadastrado(s) — pulando importação do Supabase.")
        return

    log("Banco local vazio — dá pra puxar os dados do Supabase agora.")
    if not sys.stdin.isatty():
        aviso("terminal não interativo — pulando a pergunta. Rode depois: python install.py importar-supabase")
        return

    resposta = input("    Importar os dados do Supabase agora? [s/N] ").strip().lower()
    if resposta not in ("s", "sim", "y", "yes"):
        aviso("importação pulada. Pode rodar depois: python install.py importar-supabase")
        return

    cmd_importar_supabase(argparse.Namespace(source=origem))


def cmd_superusuario(args: argparse.Namespace) -> None:
    log("Criando superusuário (acesso a /admin/ e /painel/)")
    manage("createsuperuser")


def cmd_seed(args: argparse.Namespace) -> None:
    log("Populando dados de demonstração")
    aviso("seed_demo_data cria cursos genéricos de exemplo — não é conteúdo real do cliente.")
    manage("seed_demo_data")


def cmd_rodar(args: argparse.Namespace) -> None:
    log(f"Servidor de desenvolvimento em http://{args.bind}")
    manage("runserver", args.bind)


def cmd_servir(args: argparse.Namespace) -> None:
    """Gunicorn em primeiro plano — útil pra testar antes do systemd."""
    gunicorn = venv_bin("gunicorn")
    if not gunicorn.exists():
        erro("gunicorn não instalado no venv. Rode: python install.py setup")
    log(f"Gunicorn em http://{args.bind}")
    run([
        gunicorn, "config.wsgi:application",
        "--bind", args.bind,
        "--workers", GUNICORN_WORKERS,
        "--threads", GUNICORN_THREADS,
        "--worker-class", "gthread",
        "--timeout", "60",
        "--access-logfile", "-",
    ])


def cmd_servico(args: argparse.Namespace) -> None:
    """Gera e instala systemd + nginx (Ubuntu, precisa de sudo)."""
    if not eh_ubuntu():
        aviso("Só Ubuntu. Gerando os arquivos em ./deploy/ mesmo assim, pra conferência.")

    dominio = (args.domain or "_").replace("https://", "").replace("http://", "").strip("/")
    usuario = args.system_user
    DEPLOY_DIR.mkdir(exist_ok=True)

    servico = f"""[Unit]
Description={APP_NAME} (Django + Gunicorn)
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=notify
User={usuario}
Group={usuario}
WorkingDirectory={BASE_DIR}
Environment=PYTHONUNBUFFERED=1
Environment=DJANGO_SETTINGS_MODULE=config.settings
ExecStart={venv_bin('gunicorn')} config.wsgi:application \\
    --bind 127.0.0.1:8000 \\
    --workers {GUNICORN_WORKERS} \\
    --threads {GUNICORN_THREADS} \\
    --worker-class gthread \\
    --timeout 60 \\
    --max-requests 800 \\
    --max-requests-jitter 100 \\
    --access-logfile - \\
    --error-logfile -
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=5
KillMode=mixed

# Endurecimento básico
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full

[Install]
WantedBy=multi-user.target
"""

    nginx = f"""server {{
    listen 80;
    listen [::]:80;
    server_name {dominio}{f' www.{dominio}' if dominio != '_' else ''};

    client_max_body_size 10m;
    access_log /var/log/nginx/{APP_NAME}.access.log;
    error_log  /var/log/nginx/{APP_NAME}.error.log;

    # Django não serve estáticos com DEBUG=False — o nginx serve direto.
    location /static/ {{
        alias {STATIC_ROOT}/;
        expires 30d;
        access_log off;
    }}

    location /media/ {{
        alias {BASE_DIR / 'media'}/;
        expires 7d;
        access_log off;
    }}

    location / {{
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_read_timeout 60s;
    }}
}}
"""

    arq_servico = DEPLOY_DIR / f"{APP_NAME}.service"
    arq_nginx = DEPLOY_DIR / f"{APP_NAME}.nginx.conf"
    arq_servico.write_text(servico, encoding="utf-8")
    arq_nginx.write_text(nginx, encoding="utf-8")
    ok(f"gerado {arq_servico}")
    ok(f"gerado {arq_nginx}")

    if not eh_ubuntu():
        return
    if not is_root():
        aviso("Sem root — arquivos gerados mas não instalados.")
        print(f"    Instale com: sudo python3 install.py servico --domain {dominio}")
        return

    log("Instalando serviço systemd")
    shutil.copy(arq_servico, f"/etc/systemd/system/{APP_NAME}.service")
    run(["systemctl", "daemon-reload"])
    run(["systemctl", "enable", APP_NAME])
    run(["systemctl", "restart", APP_NAME])
    run(["systemctl", "--no-pager", "status", APP_NAME], check=False)

    log("Instalando site no Nginx")
    shutil.copy(arq_nginx, f"/etc/nginx/sites-available/{APP_NAME}")
    link = Path(f"/etc/nginx/sites-enabled/{APP_NAME}")
    if not link.exists():
        link.symlink_to(f"/etc/nginx/sites-available/{APP_NAME}")
    padrao = Path("/etc/nginx/sites-enabled/default")
    if padrao.exists():
        padrao.unlink()
        aviso("site 'default' do nginx removido")
    run(["nginx", "-t"])
    run(["systemctl", "reload", "nginx"])

    # O nginx (www-data) precisa atravessar os diretórios até os estáticos.
    run(["chmod", "o+x", str(BASE_DIR)], check=False)

    print("\n" + "-" * 70)
    print("Serviço no ar. Verificação e HTTPS:")
    print(f"  systemctl status {APP_NAME}")
    print(f"  journalctl -u {APP_NAME} -f")
    print(f"  curl -I http://127.0.0.1:8000/")
    if dominio != "_":
        print(f"\n  HTTPS (aponte o DNS do domínio pro IP da VPS antes):")
        print(f"  sudo apt install -y certbot python3-certbot-nginx")
        print(f"  sudo certbot --nginx -d {dominio} -d www.{dominio}")
    print("-" * 70)


def cmd_atualizar(args: argparse.Namespace) -> None:
    """Deploy de código novo: git pull + deps + migrate + collectstatic + restart."""
    log("Atualizando código")
    run(["git", "pull", "--ff-only"], check=False)

    py = exigir_venv()
    log("Atualizando dependências")
    run([py, "-m", "pip", "install", "--no-cache-dir", "-r", BASE_DIR / "requirements.txt"])

    log("Migrations")
    manage("migrate", "--noinput")

    log("Estáticos")
    manage("collectstatic", "--noinput")

    if eh_ubuntu() and shutil.which("systemctl"):
        log("Reiniciando serviço")
        run(["systemctl", "restart", APP_NAME], check=False)
    ok("atualização concluída")


def cmd_backup(args: argparse.Namespace) -> None:
    """Dump do Postgres a partir da DATABASE_URL do .env."""
    url = ler_env().get("DATABASE_URL", "")
    if not url.startswith(("postgres://", "postgresql://")):
        erro("DATABASE_URL não é Postgres (ou não existe no .env).")
    if not shutil.which("pg_dump"):
        erro("pg_dump não encontrado. Instale: sudo apt install postgresql-client")

    destino = Path(args.saida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    log(f"Gerando dump em {destino}")
    run(["pg_dump", "--no-owner", "--no-acl", "-f", str(destino), url])
    ok(f"backup salvo: {destino} ({destino.stat().st_size // 1024} KB)")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Instalador do RS Central dos Cursos (Ubuntu VPS / Windows local).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    sub.add_parser("checar", help="mostra diagnóstico do ambiente")

    sub.add_parser("sistema", help="[Ubuntu/sudo] instala apt: python, postgres, nginx, build tools")

    p_banco = sub.add_parser("banco", help="[Ubuntu/sudo] cria role+database no Postgres e grava DATABASE_URL")
    p_banco.add_argument("--db-name", default=APP_NAME)
    p_banco.add_argument("--db-user", default=APP_NAME)
    p_banco.add_argument("--db-pass", default=None, help="se omitida, gera uma senha aleatória")

    p_setup = sub.add_parser("setup", help="venv + dependências + .env + migrate + collectstatic")
    p_setup.add_argument("--domain", default=None, help="domínio de produção (ALLOWED_HOSTS/CSRF)")
    p_setup.add_argument("--database-url", default=None, help="URL Postgres pronta (ex: Supabase)")
    p_setup.add_argument("--sqlite", action="store_true", help="força SQLite (teste local)")
    p_setup.add_argument("--debug", action="store_true", help="DEBUG=True (nunca em produção)")
    p_setup.add_argument(
        "--importar-de", dest="importar_de", default=None,
        help="URL do Postgres de origem (Supabase). Opcional: se SUPABASE_DATABASE_URL já estiver no "
             ".env, nem precisa passar essa flag — o setup pergunta [s/N] sozinho quando o banco local "
             "está vazio (1ª instalação). Em instalações seguintes (banco já com dado) pula direto, sem perguntar.",
    )

    p_imp = sub.add_parser(
        "importar-supabase",
        help="copia dados do Supabase (só leitura lá) pro banco local atual (DATABASE_URL do .env)",
    )
    p_imp.add_argument(
        "--source", default=None,
        help="DATABASE_URL de origem. Se omitido, usa SUPABASE_DATABASE_URL do .env",
    )

    sub.add_parser("superusuario", help="cria o admin do /painel/ e /admin/")
    sub.add_parser("seed", help="popula cursos de demonstração")

    p_rodar = sub.add_parser("rodar", help="servidor de desenvolvimento do Django")
    p_rodar.add_argument("--bind", default="127.0.0.1:8000")

    p_servir = sub.add_parser("servir", help="gunicorn em primeiro plano (teste de produção)")
    p_servir.add_argument("--bind", default="127.0.0.1:8000")

    p_servico = sub.add_parser("servico", help="[Ubuntu/sudo] gera e instala systemd + nginx")
    p_servico.add_argument("--domain", default=None)
    p_servico.add_argument("--system-user", default=os.environ.get("SUDO_USER") or "www-data",
                           help="usuário do sistema que roda o gunicorn")

    sub.add_parser("atualizar", help="git pull + deps + migrate + estáticos + restart")

    p_backup = sub.add_parser("backup", help="pg_dump do banco configurado no .env")
    p_backup.add_argument("--saida", default=f"backups/{APP_NAME}.sql")

    args = parser.parse_args()

    comandos = {
        "checar": cmd_checar,
        "sistema": cmd_sistema,
        "banco": cmd_banco,
        "setup": cmd_setup,
        "importar-supabase": cmd_importar_supabase,
        "superusuario": cmd_superusuario,
        "seed": cmd_seed,
        "rodar": cmd_rodar,
        "servir": cmd_servir,
        "servico": cmd_servico,
        "atualizar": cmd_atualizar,
        "backup": cmd_backup,
    }

    try:
        comandos[args.comando](args)
    except subprocess.CalledProcessError as exc:
        erro(f"comando falhou (código {exc.returncode}): {' '.join(str(c) for c in exc.cmd)}")
    except KeyboardInterrupt:
        print("\nInterrompido.")
        sys.exit(130)


if __name__ == "__main__":
    main()

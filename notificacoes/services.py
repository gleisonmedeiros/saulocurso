import logging
from abc import ABC, abstractmethod

from django.core.mail import get_connection, send_mail
from django.urls import reverse
from django.utils import timezone

from .emails import render as render_email
from .models import ConfiguracaoNotificacao, ModeloEmail, NotificacaoLog

logger = logging.getLogger(__name__)


class NotificationBackend(ABC):
    @abstractmethod
    def enviar_email(self, destinatario, assunto, mensagem):
        raise NotImplementedError

    @abstractmethod
    def enviar_whatsapp(self, destinatario, mensagem):
        raise NotImplementedError


class MockNotificationBackend(NotificationBackend):
    """Não envia nada de verdade — só registra em NotificacaoLog e imprime no console."""

    def enviar_email(self, destinatario, assunto, mensagem):
        print(f"[MOCK EMAIL] Para {destinatario} | {assunto}: {mensagem}")
        NotificacaoLog.objects.create(canal="email", destinatario=destinatario, assunto=assunto, mensagem=mensagem)

    def enviar_whatsapp(self, destinatario, mensagem):
        print(f"[MOCK WHATSAPP] Para {destinatario}: {mensagem}")
        NotificacaoLog.objects.create(canal="whatsapp", destinatario=destinatario, mensagem=mensagem)


class SMTPNotificationBackend(NotificationBackend):
    """Email de verdade via SMTP (Gmail/Google Workspace) — credenciais vêm
    do ConfiguracaoNotificacao (painel), não do .env. WhatsApp continua
    mock — de verdade precisaria de uma API paga tipo Z-API/WhatsApp Business,
    fora de escopo por enquanto."""

    def __init__(self, config):
        self.config = config

    def enviar_email(self, destinatario, assunto, mensagem):
        conexao = get_connection(
            backend="django.core.mail.backends.smtp.EmailBackend",
            host=self.config.email_host,
            port=self.config.email_port,
            username=self.config.email_host_user,
            password=self.config.email_host_password,
            use_tls=self.config.email_use_tls,
        )
        try:
            send_mail(
                assunto, mensagem, self.config.email_host_user, [destinatario],
                connection=conexao, fail_silently=False,
            )
        except Exception:
            logger.exception("Falha ao enviar email pra %s (%s)", destinatario, assunto)
            raise
        NotificacaoLog.objects.create(canal="email", destinatario=destinatario, assunto=assunto, mensagem=mensagem)

    def enviar_whatsapp(self, destinatario, mensagem):
        print(f"[MOCK WHATSAPP] Para {destinatario}: {mensagem}")
        NotificacaoLog.objects.create(canal="whatsapp", destinatario=destinatario, mensagem=mensagem)


def get_notification_backend() -> NotificationBackend:
    config = ConfiguracaoNotificacao.obter()
    if config.backend == ConfiguracaoNotificacao.Backend.SMTP:
        return SMTPNotificationBackend(config)
    return MockNotificationBackend()


class NotificationService:
    def __init__(self):
        self.config = ConfiguracaoNotificacao.obter()
        self.backend = get_notification_backend()

    def _montar(self, chave, contexto):
        """Pega assunto+corpo do modelo (painel ou padrão) e aplica os
        placeholders do contexto."""
        assunto, corpo = ModeloEmail.texto(chave)
        return render_email(assunto, contexto), render_email(corpo, contexto)

    def _portal_login(self):
        return f"{(self.config.site_url or '').rstrip('/')}{reverse('accounts:login')}"

    def notificar_matricula(self, aluno, curso):
        perfil = getattr(aluno, "perfil", None)
        telefone = getattr(perfil, "telefone", "") or "-"
        nome = aluno.get_full_name() or aluno.get_username()
        preco = getattr(curso, "preco", None)
        valor = f"R$ {preco:.2f}".replace(".", ",") if preco is not None else "-"

        assunto, mensagem_aluno = self._montar("matricula_aluno", {"nome": nome, "curso": curso.titulo})
        assunto_admin, mensagem_admin = self._montar("matricula_admin", {
            "nome": nome, "email": aluno.email or "-", "telefone": telefone,
            "login": aluno.get_username(), "curso": curso.titulo, "valor": valor,
        })

        self.backend.enviar_email(aluno.email or aluno.get_username(), assunto, mensagem_aluno)
        self.backend.enviar_whatsapp(telefone if telefone != "-" else aluno.get_username(), mensagem_aluno)

        self.backend.enviar_email(self.config.email_destino_admin(), assunto_admin, mensagem_admin)

    def notificar_credenciais(self, aluno, senha_temporaria):
        nome = aluno.get_full_name() or aluno.get_username()
        assunto, mensagem = self._montar("credenciais", {
            "nome": nome, "login": aluno.get_username(),
            "senha": senha_temporaria, "portal": self._portal_login(),
        })
        self.backend.enviar_email(aluno.email, assunto, mensagem)

    def notificar_codigo_recuperacao(self, aluno, codigo):
        nome = aluno.get_full_name() or aluno.get_username()
        assunto, mensagem = self._montar("codigo_recuperacao", {"nome": nome, "codigo": codigo})
        self.backend.enviar_email(aluno.email, assunto, mensagem)

    def notificar_mentoria(self, mentoria):
        """Avisa por email os alunos com matrícula ativa (e conta ativa) no
        curso da mentoria. Retorna quantos emails foram disparados."""
        from matriculas.models import Matricula

        curso = mentoria.curso
        portal_url = self._portal_login()
        quando = timezone.localtime(mentoria.data_hora).strftime("%d/%m/%Y às %H:%M") if mentoria.data_hora else "a definir"

        matriculas = (
            Matricula.objects.filter(curso=curso, ativo=True, aluno__is_active=True)
            .select_related("aluno")
        )
        enviados = 0
        for matricula in matriculas:
            aluno = matricula.aluno
            if not aluno.email:
                continue
            nome = aluno.get_full_name() or aluno.get_username()
            assunto, mensagem = self._montar("mentoria", {
                "nome": nome, "curso": curso.titulo, "titulo": mentoria.titulo,
                "data": quando, "descricao": getattr(mentoria, "descricao", "") or "",
                "link": getattr(mentoria, "link_reuniao", "") or "", "portal": portal_url,
            })
            self.backend.enviar_email(aluno.email, assunto, mensagem)
            enviados += 1
        return enviados

    def notificar_ingresso_turma(self, aluno, turma):
        """Manda o link do grupo/informações de acesso pro aluno que acabou
        de ingressar na turma. Só é chamado depois do clique em "Ingressar"."""
        curso = turma.curso
        nome = aluno.get_full_name() or aluno.get_username()
        nome_turma = turma.nome_exibicao()
        quando = timezone.localtime(turma.data_inicio).strftime("%d/%m/%Y às %H:%M") if turma.data_inicio else "a definir"
        assunto, mensagem = self._montar("ingresso_turma", {
            "nome": nome, "curso": curso.titulo, "turma": nome_turma, "data": quando,
            "local": turma.local_ou_modalidade or "", "whatsapp": turma.link_grupo_whatsapp or "",
            "info": turma.informacoes_acesso or "",
        })
        self.backend.enviar_email(aluno.email, assunto, mensagem)

    def notificar_turma_aberta(self, interessados, turma):
        """Avisa quem pediu aviso (InteresseTurma) que abriu turma nova com
        vaga pro curso. Retorna quantos emails foram disparados."""
        curso = turma.curso
        nome_turma = turma.nome_exibicao()
        base = (self.config.site_url or "").rstrip("/")
        portal_url = f"{base}{reverse('cursos:conteudo', args=[curso.slug])}"
        quando = timezone.localtime(turma.data_inicio).strftime("%d/%m/%Y às %H:%M") if turma.data_inicio else "a definir"
        enviados = 0
        for interesse in interessados:
            aluno = interesse.aluno
            if not aluno.email:
                continue
            nome = aluno.get_full_name() or aluno.get_username()
            assunto, mensagem = self._montar("turma_aberta", {
                "nome": nome, "curso": curso.titulo, "turma": nome_turma,
                "data": quando, "link": portal_url,
            })
            self.backend.enviar_email(aluno.email, assunto, mensagem)
            enviados += 1
        return enviados

    def enviar_comunicado(self, alunos, assunto, mensagem):
        """Envia um comunicado manual (assunto + texto livre) pra uma lista de
        alunos. Retorna quantos emails foram disparados."""
        enviados = 0
        for aluno in alunos:
            if not aluno.email:
                continue
            nome = aluno.get_full_name() or aluno.get_username()
            corpo = (
                f"Olá {nome},\n\n"
                f"{mensagem}\n\n"
                "Equipe RS Central dos Cursos"
            )
            self.backend.enviar_email(aluno.email, assunto, corpo)
            enviados += 1
        return enviados

    def notificar_contato(self, contato_mensagem):
        chave = "contato_empresa" if contato_mensagem.tipo == contato_mensagem.Tipo.EMPRESA else "contato"
        assunto, mensagem = self._montar(chave, {
            "email": contato_mensagem.email,
            "telefone": contato_mensagem.telefone or "-",
            "mensagem": contato_mensagem.mensagem,
        })
        self.backend.enviar_email(self.config.email_destino_admin(), assunto, mensagem)

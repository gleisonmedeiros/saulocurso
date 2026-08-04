import logging
from abc import ABC, abstractmethod

from django.conf import settings
from django.core.mail import get_connection, send_mail

from .models import ConfiguracaoNotificacao, NotificacaoLog

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
        self.backend = get_notification_backend()

    def notificar_matricula(self, aluno, curso):
        assunto = f"Inscrição confirmada — {curso.titulo}"
        mensagem_aluno = f"Olá {aluno.get_full_name() or aluno.get_username()}, sua inscrição no curso '{curso.titulo}' foi confirmada!"
        mensagem_admin = f"Nova matrícula: {aluno.get_username()} se inscreveu em '{curso.titulo}'."

        self.backend.enviar_email(aluno.email or aluno.get_username(), assunto, mensagem_aluno)
        telefone = getattr(getattr(aluno, "perfil", None), "telefone", "") or aluno.get_username()
        self.backend.enviar_whatsapp(telefone, mensagem_aluno)

        self.backend.enviar_email(settings.ADMIN_NOTIFICATION_EMAIL, assunto, mensagem_admin)

    def notificar_credenciais(self, aluno, senha_temporaria):
        assunto = "Seu acesso à plataforma RS Central dos Cursos"
        mensagem = (
            f"Olá {aluno.get_full_name() or aluno.get_username()}, seu cadastro foi concluído.\n\n"
            f"Login: {aluno.username}\n"
            f"Senha temporária: {senha_temporaria}\n\n"
            f"No primeiro acesso você vai precisar trocar essa senha."
        )
        self.backend.enviar_email(aluno.email, assunto, mensagem)

    def notificar_contato(self, contato_mensagem):
        if contato_mensagem.tipo == contato_mensagem.Tipo.EMPRESA:
            assunto = "Novo pedido de orçamento — Empresas"
        else:
            assunto = "Nova mensagem de contato pelo site"
        mensagem = (
            f"Email: {contato_mensagem.email}\n"
            f"Telefone: {contato_mensagem.telefone or '-'}\n\n"
            f"{contato_mensagem.mensagem}"
        )
        self.backend.enviar_email(settings.ADMIN_NOTIFICATION_EMAIL, assunto, mensagem)

from abc import ABC, abstractmethod

from django.conf import settings

from .models import NotificacaoLog


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


_BACKENDS = {
    "mock": MockNotificationBackend,
}


def get_notification_backend() -> NotificationBackend:
    nome = getattr(settings, "NOTIFICATION_BACKEND", "mock")
    backend_cls = _BACKENDS.get(nome, MockNotificationBackend)
    return backend_cls()


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
        assunto = "Seu acesso à plataforma Saulo Curso"
        mensagem = (
            f"Olá {aluno.get_full_name() or aluno.get_username()}, seu cadastro foi concluído.\n\n"
            f"Login: {aluno.username}\n"
            f"Senha temporária: {senha_temporaria}\n\n"
            f"No primeiro acesso você vai precisar trocar essa senha."
        )
        self.backend.enviar_email(aluno.email, assunto, mensagem)

    def notificar_contato(self, contato_mensagem):
        assunto = "Nova mensagem de contato pelo site"
        mensagem = (
            f"Email: {contato_mensagem.email}\n"
            f"Telefone: {contato_mensagem.telefone or '-'}\n\n"
            f"{contato_mensagem.mensagem}"
        )
        self.backend.enviar_email(settings.ADMIN_NOTIFICATION_EMAIL, assunto, mensagem)

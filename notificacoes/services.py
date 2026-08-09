import logging
from abc import ABC, abstractmethod

from django.core.mail import get_connection, send_mail
from django.urls import reverse

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
        self.config = ConfiguracaoNotificacao.obter()
        self.backend = get_notification_backend()

    def notificar_matricula(self, aluno, curso):
        assunto = f"Inscrição confirmada — {curso.titulo}"
        mensagem_aluno = f"Olá {aluno.get_full_name() or aluno.get_username()}, sua inscrição no curso '{curso.titulo}' foi confirmada!"

        perfil = getattr(aluno, "perfil", None)
        telefone = getattr(perfil, "telefone", "") or "-"
        nome = aluno.get_full_name() or aluno.get_username()
        preco = getattr(curso, "preco", None)
        valor = f"R$ {preco:.2f}".replace(".", ",") if preco is not None else "-"
        assunto_admin = f"Nova matrícula — {curso.titulo}"
        mensagem_admin = (
            "Uma nova matrícula foi registrada na plataforma.\n\n"
            "── Aluno ──\n"
            f"Nome: {nome}\n"
            f"Email: {aluno.email or '-'}\n"
            f"Telefone: {telefone}\n"
            f"Usuário: {aluno.get_username()}\n\n"
            "── Curso ──\n"
            f"Título: {curso.titulo}\n"
            f"Valor: {valor}\n\n"
            "Acesse o painel para mais detalhes."
        )

        self.backend.enviar_email(aluno.email or aluno.get_username(), assunto, mensagem_aluno)
        self.backend.enviar_whatsapp(telefone if telefone != "-" else aluno.get_username(), mensagem_aluno)

        self.backend.enviar_email(self.config.email_destino_admin(), assunto_admin, mensagem_admin)

    def notificar_credenciais(self, aluno, senha_temporaria):
        assunto = "Seu acesso ao Portal do Aluno — RS Central dos Cursos"
        base = (self.config.site_url or "").rstrip("/")
        portal_url = f"{base}{reverse('accounts:login')}"
        nome = aluno.get_full_name() or aluno.get_username()
        mensagem = (
            f"Olá {nome}, seu cadastro foi concluído com sucesso!\n\n"
            "Já pode acessar o Portal do Aluno e começar seus estudos.\n\n"
            "── Seus dados de acesso ──\n"
            f"Portal do Aluno: {portal_url}\n"
            f"Usuário (login): {aluno.get_username()}\n"
            f"Senha temporária: {senha_temporaria}\n\n"
            "Por segurança, no primeiro acesso o sistema vai pedir para você "
            "trocar essa senha temporária por uma senha pessoal.\n\n"
            "Bons estudos!\n"
            "Equipe RS Central dos Cursos"
        )
        self.backend.enviar_email(aluno.email, assunto, mensagem)

    def notificar_codigo_recuperacao(self, aluno, codigo):
        assunto = "Código para redefinir sua senha — RS Central dos Cursos"
        nome = aluno.get_full_name() or aluno.get_username()
        mensagem = (
            f"Olá {nome},\n\n"
            "Recebemos um pedido para redefinir a senha da sua conta.\n\n"
            f"Seu código de verificação é: {codigo}\n\n"
            "Ele expira em 15 minutos. Digite esse código na tela de recuperação "
            "para criar uma nova senha.\n\n"
            "Se você não pediu isso, ignore este email — sua senha continua a mesma.\n\n"
            "Equipe RS Central dos Cursos"
        )
        self.backend.enviar_email(aluno.email, assunto, mensagem)

    def notificar_mentoria(self, mentoria):
        """Avisa por email os alunos com matrícula ativa (e conta ativa) no
        curso da mentoria. Retorna quantos emails foram disparados."""
        from django.utils import timezone
        from matriculas.models import Matricula

        curso = mentoria.curso
        base = (self.config.site_url or "").rstrip("/")
        portal_url = f"{base}{reverse('accounts:login')}"
        quando = timezone.localtime(mentoria.data_hora).strftime("%d/%m/%Y às %H:%M") if mentoria.data_hora else "a definir"
        assunto = f"Nova mentoria ao vivo — {curso.titulo}"

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
            mensagem = (
                f"Olá {nome},\n\n"
                f"Uma mentoria ao vivo foi agendada no curso \"{curso.titulo}\":\n\n"
                f"{mentoria.titulo}\n"
                f"Data: {quando}\n"
            )
            if getattr(mentoria, "descricao", ""):
                mensagem += f"\n{mentoria.descricao}\n"
            if getattr(mentoria, "link_reuniao", ""):
                mensagem += f"\nLink da reunião: {mentoria.link_reuniao}\n"
            mensagem += (
                f"\nAcesse o Portal do Aluno: {portal_url}\n\n"
                "Bons estudos!\n"
                "Equipe RS Central dos Cursos"
            )
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
        if contato_mensagem.tipo == contato_mensagem.Tipo.EMPRESA:
            assunto = "Novo pedido de orçamento — Empresas"
        else:
            assunto = "Nova mensagem de contato pelo site"
        mensagem = (
            f"Email: {contato_mensagem.email}\n"
            f"Telefone: {contato_mensagem.telefone or '-'}\n\n"
            f"{contato_mensagem.mensagem}"
        )
        self.backend.enviar_email(self.config.email_destino_admin(), assunto, mensagem)

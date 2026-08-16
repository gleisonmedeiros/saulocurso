"""Registro dos modelos de email editáveis pelo painel.

Cada modelo tem um assunto e um corpo padrão (o texto atual, embutido) e uma
lista de placeholders disponíveis. O admin pode sobrescrever assunto/corpo em
notificacoes.ModeloEmail; se deixar em branco, cai no padrão daqui.

Placeholders usam chaves entre {chaves}. Um placeholder desconhecido é
deixado como está (não quebra o envio)."""


class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def render(texto, contexto):
    """Substitui os {placeholders} do texto pelos valores do contexto.
    Nunca levanta erro por placeholder faltando."""
    try:
        return texto.format_map(_SafeDict(contexto))
    except Exception:
        return texto


ASSINATURA = "Equipe RS Central dos Cursos"

MODELOS = {
    "credenciais": {
        "nome": "Boas-vindas / credenciais de acesso",
        "descricao": "Enviado ao aluno após o cadastro, com login e senha temporária.",
        "placeholders": ["nome", "login", "senha", "portal"],
        "assunto": "Seu acesso ao Portal do Aluno — RS Central dos Cursos",
        "corpo": (
            "Olá {nome}, seu cadastro foi concluído com sucesso!\n\n"
            "Já pode acessar o Portal do Aluno e começar seus estudos.\n\n"
            "── Seus dados de acesso ──\n"
            "Portal do Aluno: {portal}\n"
            "Usuário (login): {login}\n"
            "Senha temporária: {senha}\n\n"
            "Por segurança, no primeiro acesso o sistema vai pedir para você "
            "trocar essa senha temporária por uma senha pessoal.\n\n"
            "Bons estudos!\n" + ASSINATURA
        ),
    },
    "codigo_recuperacao": {
        "nome": "Código de recuperação de senha",
        "descricao": "Enviado no 'esqueci a senha', com o código de verificação.",
        "placeholders": ["nome", "codigo"],
        "assunto": "Código para redefinir sua senha — RS Central dos Cursos",
        "corpo": (
            "Olá {nome},\n\n"
            "Recebemos um pedido para redefinir a senha da sua conta.\n\n"
            "Seu código de verificação é: {codigo}\n\n"
            "Ele expira em 15 minutos. Digite esse código na tela de recuperação "
            "para criar uma nova senha.\n\n"
            "Se você não pediu isso, ignore este email — sua senha continua a mesma.\n\n"
            + ASSINATURA
        ),
    },
    "matricula_aluno": {
        "nome": "Matrícula confirmada (aluno)",
        "descricao": "Enviado ao aluno quando a inscrição no curso é confirmada.",
        "placeholders": ["nome", "curso"],
        "assunto": "Inscrição confirmada — {curso}",
        "corpo": "Olá {nome}, sua inscrição no curso '{curso}' foi confirmada!",
    },
    "matricula_admin": {
        "nome": "Nova matrícula (admin)",
        "descricao": "Enviado ao admin avisando de uma nova matrícula.",
        "placeholders": ["nome", "email", "telefone", "login", "curso", "valor"],
        "assunto": "Nova matrícula — {curso}",
        "corpo": (
            "Uma nova matrícula foi registrada na plataforma.\n\n"
            "── Aluno ──\n"
            "Nome: {nome}\n"
            "Email: {email}\n"
            "Telefone: {telefone}\n"
            "Usuário: {login}\n\n"
            "── Curso ──\n"
            "Título: {curso}\n"
            "Valor: {valor}\n\n"
            "Acesse o painel para mais detalhes."
        ),
    },
    "mentoria": {
        "nome": "Aviso de mentoria ao vivo",
        "descricao": "Enviado aos alunos do curso ao agendar/editar uma mentoria.",
        "placeholders": ["nome", "curso", "titulo", "data", "descricao", "link", "portal"],
        "assunto": "Nova mentoria ao vivo — {curso}",
        "corpo": (
            "Olá {nome},\n\n"
            "Uma mentoria ao vivo foi agendada no curso \"{curso}\":\n\n"
            "{titulo}\n"
            "Data: {data}\n"
            "{descricao}\n"
            "Link da reunião: {link}\n\n"
            "Acesse o Portal do Aluno: {portal}\n\n"
            "Bons estudos!\n" + ASSINATURA
        ),
    },
    "ingresso_turma": {
        "nome": "Ingresso em turma",
        "descricao": "Enviado ao aluno que ingressa numa turma (grupo/acesso).",
        "placeholders": ["nome", "curso", "turma", "data", "local", "whatsapp", "info"],
        "assunto": "Você ingressou em {turma} — {curso}",
        "corpo": (
            "Olá {nome},\n\n"
            "Sua vaga em \"{turma}\" ({curso}) está confirmada!\n\n"
            "Data: {data}\n"
            "Local/modalidade: {local}\n\n"
            "Grupo do WhatsApp: {whatsapp}\n\n"
            "{info}\n\n"
            "Bons estudos!\n" + ASSINATURA
        ),
    },
    "turma_aberta": {
        "nome": "Turma nova aberta (interessados)",
        "descricao": "Enviado a quem pediu aviso, quando abre turma nova.",
        "placeholders": ["nome", "curso", "turma", "data", "link"],
        "assunto": "Abriu turma nova — {curso}",
        "corpo": (
            "Olá {nome},\n\n"
            "Abriu \"{turma}\" pro curso \"{curso}\" que você pediu pra ser avisado(a):\n\n"
            "Data: {data}\n\n"
            "As vagas são limitadas — acesse o curso pra garantir a sua:\n{link}\n\n"
            + ASSINATURA
        ),
    },
    "contato": {
        "nome": "Contato pelo site (admin)",
        "descricao": "Enviado ao admin quando alguém usa o formulário de contato.",
        "placeholders": ["email", "telefone", "mensagem"],
        "assunto": "Nova mensagem de contato pelo site",
        "corpo": "Email: {email}\nTelefone: {telefone}\n\n{mensagem}",
    },
    "contato_empresa": {
        "nome": "Orçamento empresas (admin)",
        "descricao": "Enviado ao admin num pedido de orçamento de empresas.",
        "placeholders": ["email", "telefone", "mensagem"],
        "assunto": "Novo pedido de orçamento — Empresas",
        "corpo": "Email: {email}\nTelefone: {telefone}\n\n{mensagem}",
    },
}

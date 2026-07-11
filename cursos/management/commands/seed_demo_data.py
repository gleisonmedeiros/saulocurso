from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Perfil
from cursos.models import Aula, Curso, MentoriaAoVivo, Modulo
from matriculas.models import Matricula

DEMO_YOUTUBE_ID = "S9uPNppGsGo"

CURSOS_DEMO = [
    {
        "titulo": "Python do Zero ao Avançado",
        "descricao_curta": "Aprenda Python na prática, do básico à automação de tarefas reais.",
        "descricao": "Curso completo de Python cobrindo lógica de programação, orientação a objetos, "
        "manipulação de arquivos e projetos práticos. Inclui mentoria ao vivo com o instrutor.",
        "preco": "297.00",
        "imagem_tags": "programming",
        "modulos": [
            ("Fundamentos de Python", ["Instalando o ambiente", "Variáveis e tipos de dados", "Estruturas de decisão"]),
            ("Orientação a Objetos", ["Classes e objetos", "Herança e polimorfismo"]),
        ],
    },
    {
        "titulo": "Marketing Digital na Prática",
        "descricao_curta": "Estratégias reais de tráfego, conteúdo e vendas online.",
        "descricao": "Domine as ferramentas de marketing digital mais usadas no mercado: redes sociais, "
        "anúncios pagos, email marketing e funis de vendas.",
        "preco": "247.00",
        "imagem_tags": "digitalmarketing",
        "modulos": [
            ("Fundamentos de Marketing", ["Definindo seu público", "Construindo sua marca"]),
            ("Tráfego Pago", ["Introdução a anúncios", "Otimizando campanhas"]),
        ],
    },
    {
        "titulo": "Excel Avançado para Gestão",
        "descricao_curta": "Planilhas, dashboards e automação pra decisões melhores.",
        "descricao": "Aprenda fórmulas avançadas, tabelas dinâmicas, dashboards visuais e automação com "
        "macros pra ganhar produtividade na gestão do seu negócio.",
        "preco": "197.00",
        "imagem_tags": "spreadsheet",
        "modulos": [
            ("Fórmulas Avançadas", ["PROCV e ÍNDICE/CORRESP", "Fórmulas condicionais"]),
            ("Dashboards", ["Tabelas dinâmicas", "Gráficos e indicadores"]),
        ],
    },
]


class Command(BaseCommand):
    help = "Popula o banco com dados de demonstração (3 cursos, módulos, aulas, mentoria e 1 matrícula)."

    def handle(self, *args, **options):
        aluno, criado = User.objects.get_or_create(
            username="aluno.demo",
            defaults={"email": "aluno.demo@saulocurso.local", "first_name": "Aluno", "last_name": "Demo"},
        )
        if criado:
            aluno.set_password("demo12345")
            aluno.save()
        Perfil.objects.get_or_create(user=aluno, defaults={"telefone": "+55 11 90000-0000"})

        cursos_criados = []
        for i, dados in enumerate(CURSOS_DEMO):
            slug = self._slugify(dados["titulo"])
            curso, _ = Curso.objects.get_or_create(
                titulo=dados["titulo"],
                defaults={
                    "slug": slug,
                    "descricao_curta": dados["descricao_curta"],
                    "descricao": dados["descricao"],
                    "preco": dados["preco"],
                    "video_youtube_id": DEMO_YOUTUBE_ID,
                    "ativo": True,
                },
            )
            cursos_criados.append(curso)

            for m_ordem, (modulo_titulo, aulas) in enumerate(dados["modulos"]):
                modulo, _ = Modulo.objects.get_or_create(
                    curso=curso, titulo=modulo_titulo, defaults={"ordem": m_ordem}
                )
                for a_ordem, aula_titulo in enumerate(aulas):
                    aula, criada = Aula.objects.get_or_create(
                        modulo=modulo, titulo=aula_titulo, defaults={"ordem": a_ordem}
                    )
                    if criada:
                        aula.youtube_id = DEMO_YOUTUBE_ID
                        aula.save()

            MentoriaAoVivo.objects.get_or_create(
                curso=curso,
                titulo=f"Mentoria ao vivo — {curso.titulo}",
                defaults={
                    "descricao": "Encontro ao vivo pra tirar dúvidas com o instrutor.",
                    "data_hora": timezone.now() + timedelta(days=7 + i),
                    "link_reuniao": "https://meet.google.com/demo-link",
                },
            )

        Matricula.objects.get_or_create(aluno=aluno, curso=cursos_criados[0], defaults={"ativo": True})

        self.stdout.write(self.style.SUCCESS("Dados de demonstração criados."))
        self.stdout.write(f"Login do aluno demo: aluno.demo / senha: demo12345")
        self.stdout.write(f"Matriculado em: {cursos_criados[0].titulo}")

    @staticmethod
    def _slugify(titulo):
        from django.utils.text import slugify

        return slugify(titulo)

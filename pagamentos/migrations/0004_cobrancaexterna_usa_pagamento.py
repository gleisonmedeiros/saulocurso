from django.db import migrations, models
import django.db.models.deletion


def limpar_cobrancas_antigas(apps, schema_editor):
    """A CobrancaExterna antiga referenciava curso/aluno direto; a nova
    referencia um Pagamento. Não dá pra migrar automaticamente (o Pagamento
    correspondente pode nem existir ainda pro fluxo antigo) — como isso é
    só rastreio de cobrança em andamento (não é registro financeiro
    definitivo, esse é o Pagamento), limpa e recomeça do zero."""
    CobrancaExterna = apps.get_model("pagamentos", "CobrancaExterna")
    CobrancaExterna.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("pagamentos", "0003_configuracaopagamento"),
    ]

    operations = [
        migrations.RunPython(limpar_cobrancas_antigas, migrations.RunPython.noop),
        migrations.RemoveField(model_name="cobrancaexterna", name="aluno"),
        migrations.RemoveField(model_name="cobrancaexterna", name="curso"),
        migrations.RemoveField(model_name="cobrancaexterna", name="metodo"),
        migrations.RemoveField(model_name="cobrancaexterna", name="valor"),
        migrations.AddField(
            model_name="cobrancaexterna",
            name="pagamento",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="cobranca_externa",
                to="pagamentos.pagamento",
                null=True,
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="cobrancaexterna",
            name="pagamento",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="cobranca_externa",
                to="pagamentos.pagamento",
            ),
        ),
    ]

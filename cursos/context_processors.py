from .models import ConfiguracaoSite


def configuracao_site(request):
    return {"config_site": ConfiguracaoSite.obter()}

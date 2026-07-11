from django.shortcuts import redirect
from django.urls import reverse

EXEMPT_URL_NAMES = ["accounts:trocar_senha", "accounts:logout"]
EXEMPT_PATH_PREFIXES = ["/admin/", "/static/", "/media/"]


class ForcarTrocaSenhaMiddleware:
    """Redireciona pra troca de senha enquanto perfil.deve_trocar_senha estiver True."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_paths = None

    def __call__(self, request):
        if self.exempt_paths is None:
            self.exempt_paths = {reverse(name) for name in EXEMPT_URL_NAMES}

        user = request.user
        deve_trocar = user.is_authenticated and getattr(getattr(user, "perfil", None), "deve_trocar_senha", False)

        if deve_trocar and request.path not in self.exempt_paths and not any(
            request.path.startswith(prefix) for prefix in EXEMPT_PATH_PREFIXES
        ):
            return redirect("accounts:trocar_senha")

        return self.get_response(request)

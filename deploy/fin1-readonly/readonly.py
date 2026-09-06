"""Hard read-only boundary and trusted archive identity for Fin1."""
from django.contrib.auth import get_user_model
from django.http import HttpResponseForbidden, HttpResponseNotAllowed


class ArchiveUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.user = get_user_model().objects.filter(is_active=True).order_by(
            "-is_superuser", "id").first()
        if request.user is None:
            return HttpResponseForbidden("Fin1 não possui usuário ativo para consulta.")
        return self.get_response(request)


class ReadOnlyArchiveMiddleware:
    blocked_tokens = ("criar", "editar", "excluir", "recalcular", "importar",
                      "processar", "migrar", "atualizar", "staging")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            return HttpResponseNotAllowed(("GET", "HEAD", "OPTIONS"),
                "Fin1 está arquivado em modo somente leitura.")
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        name = request.resolver_match.url_name or ""
        if any(token in name for token in self.blocked_tokens):
            return HttpResponseForbidden("Esta ação está desabilitada no Fin1 somente leitura.")
        return None

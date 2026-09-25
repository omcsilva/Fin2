class PrivateResponses:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Cache-Control"] = "private, no-store"
        response["Referrer-Policy"] = "same-origin"
        response.setdefault("Content-Security-Policy",
                            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; object-src 'none'; frame-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'self'")
        return response

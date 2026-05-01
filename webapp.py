from microdot import Microdot, Response, send_file

app = Microdot()
Response.default_content_type = "application/json"

_state_provider = None


def set_state_provider(provider_callable):
    global _state_provider
    _state_provider = provider_callable


@app.get("/")
def index(request):
    return send_file("index.html")


@app.get("/api/status")
def api_status(request):
    if _state_provider is None:
        return {"error": "state unavailable"}, 503
    return _state_provider()


def run_web_server(host="0.0.0.0", port=80):
    app.run(host=host, port=port, debug=False)

from climapp_etl import web


def test_sin_redis_no_intenta_renovar(monkeypatch):
    monkeypatch.setattr(web.redis, "configured", lambda: False)
    assert web.revalidar() is False


def test_publica_clave_y_la_envia(monkeypatch):
    publicado, enviado = {}, {}
    monkeypatch.setattr(web.redis, "configured", lambda: True)
    monkeypatch.setattr(web.redis, "publish", lambda items, ttl_seconds=None: publicado.update(items, ttl=ttl_seconds))

    class Resp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout):
        enviado["url"], enviado["cuerpo"] = req.full_url, req.data
        return Resp()

    monkeypatch.setattr(web.urllib.request, "urlopen", fake_urlopen)
    assert web.revalidar() is True
    token = publicado["revalidar"]["token"]
    assert publicado["ttl"] == 300 and len(token) > 30
    assert enviado["url"].endswith("/api/revalidate") and token.encode() in enviado["cuerpo"]


def test_error_de_red_no_rompe_la_ingesta(monkeypatch):
    monkeypatch.setattr(web.redis, "configured", lambda: True)
    monkeypatch.setattr(web.redis, "publish", lambda *a, **k: 1)
    monkeypatch.setattr(web.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("sin red")))
    assert web.revalidar() is False

import base64
import gzip
import json

from climapp_etl import redis


def _decodificar(v: str):
    return json.loads(gzip.decompress(base64.b64decode(v[3:])) if v.startswith("gz:") else v)


def test_valores_grandes_van_comprimidos_y_los_chicos_no():
    chico = {"a": 1}
    grande = {"horas": [{"hora": f"2026-10-29T{h:02d}:00", "temperatura": 15.5} for h in range(24)] * 10}
    assert redis.codificar(chico) == '{"a":1}'
    g = redis.codificar(grande)
    assert g.startswith("gz:") and _decodificar(g) == grande
    assert len(g) < len(json.dumps(grande)) / 3


def test_mset_por_lotes_y_set_con_plazo():
    items = {f"loc:{i}": {"x": "y" * 3000, "i": i} for i in range(50)}
    cmds = redis.comandos(items)
    assert all(c[0] == "MSET" for c in cmds)
    claves = [k for c in cmds for k in c[1::2]]
    assert claves == [f"{redis.PREFIX}:loc:{i}" for i in range(50)]
    assert all(sum(len(x) for x in c[1:]) <= redis.LOTE_BYTES for c in cmds)
    assert _decodificar(cmds[0][2]) == items["loc:0"]
    assert redis.comandos({"revalidar": {"token": "t"}}, ttl_seconds=300) == [
        ["SET", f"{redis.PREFIX}:revalidar", '{"token":"t"}', "EX", "300"]]


def test_respaldo_en_archivos_aunque_redis_falle(tmp_path, monkeypatch):
    monkeypatch.setenv("CLIMAPP_RESPALDO_DIR", str(tmp_path))
    monkeypatch.setattr(redis, "_config", lambda: ("http://127.0.0.1:9", "x"))   # Redis inalcanzable
    datos = {"loc:quintero": {"t": "Quintero ñ"}, "avisos": {"avisos": []}}
    try:
        redis.publish(datos)
    except OSError:
        pass
    assert json.loads((tmp_path / "loc" / "quintero.json").read_text(encoding="utf-8")) == datos["loc:quintero"]
    assert (tmp_path / "avisos.json").exists()
    assert redis.ruta_respaldo("lugares:puerto-quintero") == "lugares/puerto-quintero.json"


def test_sin_redis_cuenta_las_respaldadas(tmp_path, monkeypatch):
    monkeypatch.setenv("CLIMAPP_RESPALDO_DIR", str(tmp_path))
    monkeypatch.setattr(redis, "_config", lambda: None)
    assert redis.publish({"lluvia": {"a": 1}}) == 1
    assert redis.publish({"revalidar": {"token": "t"}}, ttl_seconds=300) == 0
    assert not (tmp_path / "revalidar.json").exists()


def test_cuota_agotada_no_falla_y_deja_de_intentar(tmp_path, monkeypatch):
    import io
    import urllib.error
    monkeypatch.setenv("CLIMAPP_RESPALDO_DIR", str(tmp_path))
    monkeypatch.setattr(redis, "_config", lambda: ("https://x", "t"))
    monkeypatch.setattr(redis, "_sin_cuota", False)
    llamadas = []

    def rechaza(request, timeout):
        llamadas.append(request)
        raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, io.BytesIO(
            b'{"error":"ERR This database has reached current Fixed plan limits."}'))
    monkeypatch.setattr(redis.urllib.request, "urlopen", rechaza)
    assert redis.publish({"avisos": {"x": 1}}) == 1
    assert redis.sin_cuota()
    assert redis.publish({"lluvia": {"x": 2}}) == 1 and len(llamadas) == 1
    assert (tmp_path / "lluvia.json").exists()
    assert not redis.es_cuota_agotada(403, '{"error":"WRONGPASS"}')


def test_con_respaldo_las_claves_por_ubicacion_no_van_a_redis(tmp_path, monkeypatch):
    monkeypatch.setenv("CLIMAPP_RESPALDO_DIR", str(tmp_path))
    monkeypatch.setattr(redis, "_config", lambda: ("https://x", "t"))
    monkeypatch.setattr(redis, "_sin_cuota", False)
    enviados = []

    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return b'[{"result":"OK"}]'

    monkeypatch.setattr(redis.urllib.request, "urlopen",
                        lambda req, timeout: enviados.append(json.loads(req.data)) or Resp())
    assert redis.publish({"loc:quintero": {"a": 1}, "lugares:quintero": {"b": 2}}) == 2
    assert enviados == [] and (tmp_path / "lugares" / "quintero.json").exists()
    redis.publish({"loc:arica": {"a": 1}, "avisos": {"avisos": []}})
    claves = [k for cmd in enviados for k in cmd[0][1::2]]
    assert claves == [f"{redis.PREFIX}:avisos"]

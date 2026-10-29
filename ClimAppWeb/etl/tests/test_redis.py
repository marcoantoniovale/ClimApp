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

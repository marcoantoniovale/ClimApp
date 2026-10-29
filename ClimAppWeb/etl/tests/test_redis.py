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

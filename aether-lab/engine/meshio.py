"""Read 3D mesh files on the server (numpy only): STL (binary / ASCII), OBJ, glTF binary (.glb) and glTF (.gltf with
embedded buffers). Returns one triangle mesh (V in mm, F) with every node transform applied. glTF is metres and Y up,
so it is converted to mm, Z up (the scene frame): (x, y, z) m -> (x, -z, y) * 1000."""
import base64
import json
import struct
from pathlib import Path

import numpy as np


def load(path):
    p = Path(path)
    ext = p.suffix.lower()
    data = p.read_bytes()
    if ext == ".stl":
        return _stl(data)
    if ext == ".obj":
        return _obj(data.decode("utf-8", errors="ignore"))
    if ext == ".glb":
        return _glb(data)
    if ext == ".gltf":
        doc = json.loads(data.decode("utf-8"))
        bufs = []
        for b in doc.get("buffers", []):
            uri = b.get("uri", "")
            if uri.startswith("data:"):
                bufs.append(base64.b64decode(uri.split(",", 1)[1]))
            else:
                bufs.append((p.parent / uri).read_bytes())
        return _gltf(doc, bufs)
    raise ValueError(f"unsupported mesh format {ext}")


def _stl(data):
    if data[:5].lower() == b"solid" and b"facet" in data[:400]:
        V = np.array([[float(x) for x in ln.split()[1:4]] for ln in data.decode(errors="ignore").splitlines()
                      if ln.strip().startswith("vertex")])
    else:
        n = struct.unpack("<I", data[80:84])[0]
        rec = np.frombuffer(data[84:84 + 50 * n], dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
        V = rec["v"].reshape(-1, 3).astype(float)
    return _weld(V)


def _weld(V):
    key = np.round(V, 5)
    uniq, inv = np.unique(key, axis=0, return_inverse=True)
    F = inv.reshape(-1, 3)
    F = F[(F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])]
    return uniq.astype(float), F.astype(int)


def _obj(text):
    V, F = [], []
    for ln in text.splitlines():
        t = ln.split()
        if not t:
            continue
        if t[0] == "v":
            V.append([float(x) for x in t[1:4]])
        elif t[0] == "f":
            idx = [int(x.split("/")[0]) for x in t[1:]]
            idx = [i - 1 if i > 0 else len(V) + i for i in idx]
            F += [[idx[0], idx[k], idx[k + 1]] for k in range(1, len(idx) - 1)]
    return np.asarray(V, float), np.asarray(F, int)


def _glb(data):
    magic, _, _ = struct.unpack("<4sII", data[:12])
    if magic != b"glTF":
        raise ValueError("not a GLB file")
    off, doc, bin_ = 12, None, b""
    while off < len(data):
        ln, typ = struct.unpack("<I4s", data[off:off + 8])
        chunk = data[off + 8:off + 8 + ln]
        if typ == b"JSON":
            doc = json.loads(chunk.decode("utf-8"))
        elif typ == b"BIN\x00":
            bin_ = chunk
        off += 8 + ln
    return _gltf(doc, [bin_])


_CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
_NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def _acc(doc, bufs, i):
    a = doc["accessors"][i]
    bv = doc["bufferViews"][a["bufferView"]]
    buf = bufs[bv.get("buffer", 0)]
    n, dt = _NC[a["type"]], np.dtype(_CT[a["componentType"]])
    start = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = bv.get("byteStride") or n * dt.itemsize
    raw = np.frombuffer(buf, np.uint8, count=stride * (a["count"] - 1) + n * dt.itemsize, offset=start)
    rows = np.lib.stride_tricks.as_strided(raw, (a["count"], n * dt.itemsize), (stride, 1))
    return rows.copy().view(dt).reshape(a["count"], n)


def _local(node):
    if "matrix" in node:
        return np.asarray(node["matrix"], float).reshape(4, 4).T
    M = np.eye(4)
    x, y, z, w = node.get("rotation", [0, 0, 0, 1])
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    M[:3, :3] = R @ np.diag(node.get("scale", [1, 1, 1]))
    M[:3, 3] = node.get("translation", [0, 0, 0])
    return M


def _gltf(doc, bufs):
    Vs, Fs, off = [], [], 0
    nodes = doc.get("nodes", [])
    scene = doc.get("scenes", [{}])[doc.get("scene", 0)] if doc.get("scenes") else {"nodes": list(range(len(nodes)))}

    def walk(i, M):
        nonlocal off
        node = nodes[i]
        W = M @ _local(node)
        if "mesh" in node:
            for prim in doc["meshes"][node["mesh"]]["primitives"]:
                if prim.get("mode", 4) != 4 or "POSITION" not in prim.get("attributes", {}):
                    continue
                P = _acc(doc, bufs, prim["attributes"]["POSITION"]).astype(float)
                idx = _acc(doc, bufs, prim["indices"]).ravel().astype(int) if "indices" in prim else np.arange(len(P))
                P = P @ W[:3, :3].T + W[:3, 3]
                Vs.append(P)
                Fs.append(idx.reshape(-1, 3) + off)
                off += len(P)
        for c in node.get("children", []):
            walk(c, W)
    for i in scene.get("nodes", []):
        walk(i, np.eye(4))
    if not Vs:
        raise ValueError("the glTF holds no triangle mesh")
    V = np.vstack(Vs)
    V = np.c_[V[:, 0], -V[:, 2], V[:, 1]] * 1000.0          # metres, Y up -> mm, Z up
    return V, np.vstack(Fs)

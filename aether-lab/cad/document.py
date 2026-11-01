"""The AETHER CAD document (.aethercad): the authoritative, editable model.

A document is plain JSON: parameters (with provenance), observations (measured evidence), hypotheses (stored AI
answers), datums, features (operation NAME from a fixed enum + typed params + input feature ids), components,
joints, assumptions, validation, history. B-rep shapes are derived from it by recompute() and cached in memory
(and optionally on disk as .brep); they are never the source of truth.

Parameter values (all numbers are mm / deg / plain floats):
  {"value": v}                                       literal
  {"rel": {"kind": "linear", "terms": [[pid, c], ...], "const": k}}   v = sum(c * value(pid)) + k
  {"rel": {"kind": "scaled", "ref": v_ref, "by": pid, "by_ref": r}}   v = v_ref * value(pid) / r
  {"rel": {"kind": "sample", "obs": oid, "at": pid, "by": pid, "by_ref": r}}
        v = interp(observation curve oid at value(at) * r / value(by)) * value(by) / r
        (the curve is stored at the reference scale; `at` is a model x, converted back to the reference frame)
  "override": v   replaces the computed value (provenance becomes user_confirmed); removing it restores the relation.
Only these four kinds exist; there are no expressions, so a document can not carry code.

Feature params may be literals or {"$p": pid} (a parameter) or {"$obs": oid} (an observation's data).
"""
from __future__ import annotations

import copy
import hashlib
import json
import time
import uuid

import numpy as np

SCHEMA = "aethercad/1"
PROVENANCE = ("measured", "derived", "inferred", "assumed", "unresolved", "user_confirmed", "external_reference")
MATURITY = ("draft_inference", "geometrically_valid", "drawing_consistent", "dimension_constrained",
            "assembly_checked", "engineer_reviewed")          # never set beyond drawing_consistent automatically
REL_KINDS = ("linear", "scaled", "sample")


class DocumentError(ValueError):
    """The document breaks the schema (bad field, unknown op, cycle, missing reference)."""


class RecomputeError(RuntimeError):
    def __init__(self, feature_id, message):
        super().__init__(f"{feature_id}: {message}")
        self.feature_id = feature_id
        self.message = message


# ------------------------------------------------------------------------------------------------ schema checks
def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and np.isfinite(x)


def validate_schema(doc, ops):
    """Raise DocumentError with a path for the first problem found."""
    def bad(path, msg):
        raise DocumentError(f"{path}: {msg}")
    if doc.get("schema") != SCHEMA:
        bad("schema", f"expected {SCHEMA}")
    if doc.get("units") != "mm":
        bad("units", "only mm is supported")
    P = doc.get("parameters")
    if not isinstance(P, dict):
        bad("parameters", "must be an object")
    for pid, p in P.items():
        path = f"parameters.{pid}"
        if not isinstance(p, dict):
            bad(path, "must be an object")
        if p.get("provenance") not in PROVENANCE:
            bad(path + ".provenance", f"must be one of {PROVENANCE}")
        has_v, has_r = "value" in p, "rel" in p
        if has_v == has_r:
            bad(path, "exactly one of value / rel")
        if has_v and not (_num(p["value"]) or isinstance(p["value"], (str, bool))):
            bad(path + ".value", "must be a finite number, string or bool")
        if has_r:
            r = p["rel"]
            if not isinstance(r, dict) or r.get("kind") not in REL_KINDS:
                bad(path + ".rel.kind", f"must be one of {REL_KINDS}")
            refs = []
            if r["kind"] == "linear":
                if not isinstance(r.get("terms"), list) or not _num(r.get("const", 0)):
                    bad(path + ".rel", "linear needs terms [[pid, coef]] and a numeric const")
                for t in r["terms"]:
                    if not (isinstance(t, list) and len(t) == 2 and isinstance(t[0], str) and _num(t[1])):
                        bad(path + ".rel.terms", "each term is [pid, number]")
                    refs.append(t[0])
            elif r["kind"] == "scaled":
                if not (_num(r.get("ref")) and isinstance(r.get("by"), str) and _num(r.get("by_ref")) and r["by_ref"] != 0):
                    bad(path + ".rel", "scaled needs ref, by, by_ref (non-zero)")
                refs.append(r["by"])
            else:
                if r.get("obs") not in doc.get("observations", {}):
                    bad(path + ".rel.obs", f"unknown observation {r.get('obs')!r}")
                refs += [r.get("at"), r.get("by")]
                if not _num(r.get("by_ref")):
                    bad(path + ".rel.by_ref", "number required")
            for q in refs:
                if q not in P:
                    bad(path + ".rel", f"unknown parameter {q!r}")
        if "override" in p and not _num(p["override"]):
            bad(path + ".override", "must be a finite number")
        if "range" in p:
            rg = p["range"]
            if not (isinstance(rg, list) and len(rg) == 2 and all(_num(v) for v in rg) and rg[0] <= rg[1]):
                bad(path + ".range", "[min, max]")
    ids = set()
    for i, f in enumerate(doc.get("features", [])):
        path = f"features[{i}]"
        if not isinstance(f.get("id"), str) or f["id"] in ids:
            bad(path + ".id", "missing or duplicate")
        ids.add(f["id"])
        if f.get("op") not in ops:
            bad(path + ".op", f"unknown operation {f.get('op')!r}")
        for j in f.get("inputs", []):
            if j not in ids:
                bad(path + ".inputs", f"{j!r} is not an earlier feature (features are stored in dependency order)")
        _check_values(f.get("params", {}), path + ".params", P, doc.get("observations", {}), bad)
    for c in doc.get("components", []):
        if c.get("output") not in ids:
            bad(f"components.{c.get('id')}.output", "unknown feature")
    return True


def _check_values(v, path, P, O, bad):
    if isinstance(v, dict):
        if set(v) == {"$p"}:
            if v["$p"] not in P:
                bad(path, f"unknown parameter {v['$p']!r}")
            return
        if set(v) == {"$obs"}:
            if v["$obs"] not in O:
                bad(path, f"unknown observation {v['$obs']!r}")
            return
        for k, x in v.items():
            if k.startswith("$"):
                bad(path + "." + k, "unknown reference form")
            _check_values(x, path + "." + k, P, O, bad)
    elif isinstance(v, list):
        for i, x in enumerate(v):
            _check_values(x, f"{path}[{i}]", P, O, bad)
    elif isinstance(v, str):
        if len(v) > 200:
            bad(path, "string too long")
    elif not (v is None or isinstance(v, bool) or _num(v)):
        bad(path, f"unsupported value {type(v).__name__}")


# ------------------------------------------------------------------------------------------------ document
class Document:
    def __init__(self, data, ops):
        self.data = data
        self.ops = ops
        validate_schema(data, ops)
        self.shapes = {}                    # feature id -> shape (current valid recompute)
        self.info = {}                      # feature id -> op info
        self._cache = {}                    # key -> (shape, info)
        self.stale = False

    # ---- persistence
    @staticmethod
    def new(source, title):
        return {"schema": SCHEMA, "units": "mm", "document_id": uuid.uuid4().hex, "title": title,
                "created": time.strftime("%Y-%m-%d %H:%M:%S"), "source": source, "maturity": "draft_inference",
                "decisions": {}, "parameters": {}, "observations": {}, "hypotheses": [], "datums": {}, "features": [],
                "components": [], "joints": [], "assumptions": [], "validation": {}, "history": [],
                "status": {"state": "not_built"}}

    def to_json(self):
        return json.dumps(self.data, indent=1, default=_json_default)

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    @classmethod
    def load(cls, path, ops):
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f), ops)

    # ---- parameters
    def param_values(self):
        """Resolve every parameter (relations in dependency order). Returns {pid: value}; raises DocumentError on a
        cycle."""
        P = self.data["parameters"]
        O = self.data["observations"]
        out, busy = {}, set()

        def get(pid):
            if pid in out:
                return out[pid]
            if pid in busy:
                raise DocumentError(f"parameters.{pid}: relation cycle")
            busy.add(pid)
            p = P[pid]
            if "override" in p:
                v = float(p["override"])
            elif "value" in p:
                v = p["value"]
            else:
                r = p["rel"]
                if r["kind"] == "linear":
                    v = sum(c * get(q) for q, c in r["terms"]) + r.get("const", 0.0)
                elif r["kind"] == "scaled":
                    v = r["ref"] * get(r["by"]) / r["by_ref"]
                else:
                    k = get(r["by"]) / r["by_ref"]
                    curve = np.asarray(O[r["obs"]]["data"], float)
                    v = float(np.interp(get(r["at"]) / k, curve[:, 0], curve[:, 1])) * k
            busy.discard(pid)
            out[pid] = float(v) if _num(v) else v
            return out[pid]
        for pid in P:
            get(pid)
        return out

    def param_dependents(self, pid):
        """Parameters whose value depends on pid (transitively), and the features that use any of them."""
        P = self.data["parameters"]
        deps = {pid}
        changed = True
        while changed:
            changed = False
            for q, p in P.items():
                if q in deps or "rel" not in p or "override" in p:
                    continue
                r = p["rel"]
                refs = [t[0] for t in r.get("terms", [])] + [r.get("by"), r.get("at")]
                if deps & set(x for x in refs if x):
                    deps.add(q)
                    changed = True
        feats = [f["id"] for f in self.data["features"] if _uses(f.get("params", {}), deps)]
        return deps, self.downstream(feats)

    def downstream(self, fids):
        out = list(dict.fromkeys(fids))
        for f in self.data["features"]:
            if f["id"] not in out and set(f.get("inputs", [])) & set(out):
                out.append(f["id"])
        return out

    # ---- recompute
    def resolve(self, v, PV):
        if isinstance(v, dict):
            if set(v) == {"$p"}:
                return PV[v["$p"]]
            if set(v) == {"$obs"}:
                return self.data["observations"][v["$obs"]]["data"]
            return {k: self.resolve(x, PV) for k, x in v.items()}
        if isinstance(v, list):
            return [self.resolve(x, PV) for x in v]
        return v

    def recompute(self, validate=None):
        """Rebuild every feature in order (cached by the hash of its resolved inputs). Transactional: on any
        failure the document's status says which feature failed and why, self.shapes keeps the LAST VALID result
        and self.stale is True (callers must show that geometry as stale, not current). Returns the status dict."""
        t0 = time.time()
        PV = self.param_values()
        for pid, p in self.data["parameters"].items():
            rg = p.get("range")
            v = PV[pid]
            if rg and _num(v) and not (rg[0] - 1e-9 <= v <= rg[1] + 1e-9):
                return self._fail(pid, f"value {v:.4g} outside its allowed range {rg}", t0, kind="parameter_range")
        shapes, info, keys = {}, {}, {}
        rebuilt = 0
        for f in self.data["features"]:
            fid = f["id"]
            params = self.resolve(f.get("params", {}), PV)
            key = hashlib.sha1(json.dumps([f["op"], params, [keys[i] for i in f.get("inputs", [])]],
                                          sort_keys=True, default=_json_default).encode()).hexdigest()
            keys[fid] = key
            if key in self._cache:
                shapes[fid], info[fid] = self._cache[key]
                f["status"] = "ok"
                continue
            try:
                shp, inf = self.ops[f["op"]](params, [(shapes[i], info[i]) for i in f.get("inputs", [])], self)
            except Exception as e:                                   # kernel or op error: explicit failure
                f["status"] = "failed"
                f["error"] = f"{type(e).__name__}: {e}"[:500]
                for g in self.data["features"]:
                    if g["id"] in self.downstream([fid]) and g["id"] != fid:
                        g["status"] = "blocked"
                return self._fail(fid, f["error"], t0)
            if inf.get("valid") is False and not f.get("optional"):
                f["status"] = "failed"
                f["error"] = "result is not a valid B-rep: " + str(inf.get("why", ""))[:300]
                return self._fail(fid, f["error"], t0)
            f["status"] = "ok"
            f.pop("error", None)
            self._cache[key] = (shp, inf)
            shapes[fid], info[fid] = shp, inf
            rebuilt += 1
        self.shapes, self.info, self.stale = shapes, info, False
        if len(self._cache) > 4000:
            live = set(keys.values())
            self._cache = {k: v for k, v in self._cache.items() if k in live}
        st = {"state": "ok", "rebuilt_features": rebuilt, "cached_features": len(self.data["features"]) - rebuilt,
              "seconds": round(time.time() - t0, 2), "param_hash": _hash(PV)}
        if validate:
            st["validation"] = validate(self)
            if not st["validation"]["all_valid"]:
                st["state"] = "invalid"
                self.stale = True
        self.data["status"] = st
        return st

    def _fail(self, where, msg, t0, kind="feature"):
        self.stale = bool(self.shapes)
        st = {"state": "failed", "failed": where, "kind": kind, "error": msg, "seconds": round(time.time() - t0, 2),
              "geometry_shown": "last valid (STALE)" if self.stale else "none"}
        self.data["status"] = st
        return st

    def component_shape(self, cid):
        c = next(c for c in self.data["components"] if c["id"] == cid)
        return self.shapes.get(c["output"])

    # ---- edits (transactions)
    def set_param(self, pid, value=None, clear_override=False, validate=None, note=None):
        """Edit one parameter and recompute. Literal parameters get a new value; computed ones get an override
        (provenance user_confirmed). On failure the edit is rolled back and the failure returned."""
        P = self.data["parameters"]
        if pid not in P:
            raise DocumentError(f"unknown parameter {pid!r}")
        before = copy.deepcopy(P[pid])
        p = P[pid]
        if clear_override:
            p.pop("override", None)
            p["provenance"] = p.get("provenance_before_override", p["provenance"])
        elif "value" in p and "rel" not in p:
            if not (_num(value) or isinstance(value, (str, bool))):
                raise DocumentError(f"{pid}: value must be a number")
            p["value"] = value
            p.setdefault("provenance_before_override", before["provenance"])
            p["provenance"] = "user_confirmed"
        else:
            if not _num(value):
                raise DocumentError(f"{pid}: value must be a number")
            p.setdefault("provenance_before_override", before["provenance"])
            p["override"] = float(value)
            p["provenance"] = "user_confirmed"
        deps, feats = self.param_dependents(pid)
        st = self.recompute(validate)
        entry = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "param": pid, "before": before.get("override", before.get("value")),
                 "after": value, "clear_override": clear_override, "dependent_params": len(deps) - 1,
                 "dependent_features": feats, "result": st["state"], "note": note}
        if st["state"] != "ok":
            P[pid] = before                                     # roll back the edit, keep the failure on record
            entry["rolled_back"] = True
            self.data["history"].append(entry)
            st2 = self.recompute(validate)                      # back to the last valid state (from cache)
            st["rolled_back_to"] = st2["state"]
            self.data["status"] = {**st2, "last_failed_edit": entry}
            return st
        self.data["history"].append(entry)
        return st


def _uses(params, pids):
    if isinstance(params, dict):
        if set(params) == {"$p"}:
            return params["$p"] in pids
        return any(_uses(v, pids) for v in params.values())
    if isinstance(params, list):
        return any(_uses(v, pids) for v in params)
    return False


def _hash(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=_json_default).encode()).hexdigest()[:16]


def _json_default(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(f"not JSON serialisable: {type(o).__name__}")

"""Photo-to-CAD reconstruction built from SAM/Muse observations, never from a mesh.

The SAM 3D output is intentionally not imported here. This module builds native
OpenCascade feature graphs from a constrained, reviewable CAD plan returned by
Muse. Every numeric input is a document parameter with provenance; tessellation
is generated later by the worker only for display/physics.
"""
from __future__ import annotations

import math
import re

from .document import Document
from .ops import OPS
from .validate import check_solid

_ID = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
MAX_PARTS = 24
MAX_HOLES_PER_PART = 32
MAX_DIMENSION_MM = 20000.0


def _finite(value, label, minimum=None, maximum=MAX_DIMENSION_MM):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    value = float(value)
    if minimum is not None and value < minimum:
        raise ValueError(f"{label} must be >= {minimum}")
    if maximum is not None and abs(value) > maximum:
        raise ValueError(f"{label} magnitude exceeds {maximum}")
    return value


def _vec(value, n, label, minimum=None):
    if not isinstance(value, (list, tuple)) or len(value) != n:
        raise ValueError(f"{label} must contain {n} numbers")
    return [_finite(v, f"{label}[{i}]", minimum=minimum) for i, v in enumerate(value)]


def _unit_axis(value, label):
    axis = _vec(value, 3, label)
    norm = math.sqrt(sum(v * v for v in axis))
    if norm < 1e-8:
        raise ValueError(f"{label} must be non-zero")
    return [v / norm for v in axis]


def _colour(value):
    value = str(value or "#b9c3cf")
    if len(value) != 7 or not value.startswith("#"):
        raise ValueError("colour must be #RRGGBB")
    try:
        int(value[1:], 16)
    except ValueError as exc:
        raise ValueError("colour must be #RRGGBB") from exc
    return value.lower()


def _parameter(doc, pid, value, note, evidence):
    if pid in doc.data["parameters"]:
        raise ValueError(f"duplicate CAD parameter {pid}")
    doc.data["parameters"][pid] = {
        "value": value,
        "provenance": "inferred",
        "unit": "mm",
        "note": str(note or "Inferred from the single-photo reconstruction; review before manufacturing.")[:240],
        "evidence": str(evidence or "SAM 3.1 mask + SAM 3D visual hypothesis + Muse interpretation")[:240],
    }
    return {"$p": pid}


def _refs(doc, prefix, values, note, evidence):
    return [_parameter(doc, f"{prefix}_{i}", v, note, evidence) for i, v in enumerate(values)]


def _profile_refs(doc, prefix, profile, note, evidence):
    if not isinstance(profile, list) or not 3 <= len(profile) <= 128:
        raise ValueError(f"{prefix} profile must contain 3..128 2D points")
    return [_refs(doc, f"{prefix}_pt{i}", _vec(point, 2, f"{prefix}.profile[{i}]"), note, evidence)
            for i, point in enumerate(profile)]


def _shape_spec(raw, prefix, doc, evidence):
    if not isinstance(raw, dict):
        raise ValueError(f"{prefix}.shape must be an object")
    kind = raw.get("kind")
    allowed = {"box", "cylinder", "cone", "sphere", "torus", "extrusion"}
    if kind not in allowed:
        raise ValueError(f"{prefix}: unsupported B-rep primitive {kind!r}")
    note = "Feature dimensions inferred by Muse from the photograph and SAM 3D orbit views; not measured engineering data."
    out = {"kind": kind, "origin": _refs(doc, f"{prefix}_origin", _vec(raw.get("origin"), 3, f"{prefix}.origin"), note, evidence)}
    out["axis"] = _refs(doc, f"{prefix}_axis", _unit_axis(raw.get("axis", [0, 0, 1]), f"{prefix}.axis"), note, evidence)
    if kind == "box":
        dims = _vec(raw.get("dimensions"), 3, f"{prefix}.dimensions", minimum=0.01)
        out["dimensions"] = _refs(doc, f"{prefix}_dimensions", dims, note, evidence)
    elif kind in ("cylinder", "cone", "sphere", "torus"):
        r = _finite(raw.get("radius"), f"{prefix}.radius", minimum=0.01)
        out["radius"] = _parameter(doc, f"{prefix}_radius", r, note, evidence)
        if kind in ("cone", "torus"):
            r2 = _finite(raw.get("radius2"), f"{prefix}.radius2", minimum=0.01)
            out["radius2"] = _parameter(doc, f"{prefix}_radius2", r2, note, evidence)
        if kind in ("cylinder", "cone"):
            h = _finite(raw.get("height"), f"{prefix}.height", minimum=0.01)
            out["height"] = _parameter(doc, f"{prefix}_height", h, note, evidence)
    elif kind == "extrusion":
        out["profile"] = _profile_refs(doc, prefix, raw.get("profile"), note, evidence)
        out["depth"] = _parameter(doc, f"{prefix}_depth", _finite(raw.get("depth"), f"{prefix}.depth", minimum=0.01), note, evidence)
    return out


def build(plan, out_dir=None):
    """Validate a Muse CAD plan and return (Document, report)."""
    if not isinstance(plan, dict) or not isinstance(plan.get("components"), list):
        raise ValueError("CAD plan must contain a components array")
    parts = plan["components"]
    if not 1 <= len(parts) <= MAX_PARTS:
        raise ValueError(f"CAD plan must contain 1..{MAX_PARTS} components")

    source = {
        "kind": "photo_reconstruction",
        "pipeline": ["SAM 3.1", "SAM 3D Objects (visual hypothesis)", "Muse CAD plan", "OpenCascade B-rep"],
        "sam3d_job_id": str(plan.get("sam3d_job_id") or "")[:80],
        "scale": plan.get("scale") or {"kind": "assumed", "unit": "mm"},
    }
    doc = Document(Document.new(source, str(plan.get("title") or "Photo reconstruction")[:120]), OPS)
    doc.data["assumptions"].extend(str(x)[:300] for x in (plan.get("assembly_assumptions") or [])[:40])
    seen = set()
    component_outputs = {}

    for index, part in enumerate(parts):
        if not isinstance(part, dict):
            raise ValueError(f"components[{index}] must be an object")
        pid = str(part.get("id") or f"part_{index + 1}").lower()
        if not _ID.fullmatch(pid) or pid in seen:
            raise ValueError(f"invalid or duplicate component id: {pid!r}")
        seen.add(pid)
        name = str(part.get("name") or pid.replace("_", " ").title())[:80]
        colour = _colour(part.get("colour"))
        evidence = str(part.get("evidence") or "Single photograph; the back/depth is inferred, not observed.")[:240]
        base = f"f_{pid}_base"
        shape = _shape_spec(part.get("shape"), pid, doc, evidence)
        doc.data["features"].append({
            "id": base, "op": "photo_primitive", "label": f"{name} — base feature",
            "inputs": [], "params": shape, "component": pid,
        })
        last = base

        holes = part.get("holes") or []
        if not isinstance(holes, list) or len(holes) > MAX_HOLES_PER_PART:
            raise ValueError(f"{pid}.holes must contain at most {MAX_HOLES_PER_PART} holes")
        for hi, hole in enumerate(holes):
            if not isinstance(hole, dict):
                raise ValueError(f"{pid}.holes[{hi}] must be an object")
            hid = f"{pid}_hole_{hi + 1:02d}"
            hshape = {
                "kind": "cylinder",
                "origin": hole.get("origin"),
                "axis": hole.get("axis", [0, 0, 1]),
                "radius": hole.get("radius"),
                "height": hole.get("height"),
            }
            cutter_id = f"f_{hid}_tool"
            cutter = _shape_spec(hshape, hid, doc, evidence)
            doc.data["features"].append({
                "id": cutter_id, "op": "photo_primitive", "label": f"{name} — hole tool {hi + 1}",
                "inputs": [], "params": cutter, "component": None, "auxiliary": True,
            })
            cut_id = f"f_{hid}_cut"
            doc.data["features"].append({
                "id": cut_id, "op": "photo_boolean", "label": f"{name} — hole {hi + 1}",
                "inputs": [last, cutter_id], "params": {"kind": "cut"}, "component": pid,
            })
            last = cut_id

        parent = str(part.get("parent") or "")[:80]
        doc.data["components"].append({
            "id": pid, "name": name, "kind": "body_shell", "output": last,
            "colour": colour, "parent": parent or None, "group": False,
            "provenance": "inferred",
        })
        for assumption in (part.get("assumptions") or [])[:20]:
            doc.data["assumptions"].append(f"{name}: {str(assumption)[:260]}")

    for c in doc.data["components"]:
        if c.get("parent") and c["parent"] not in seen:
            raise ValueError(f"{c['id']} references unknown parent {c['parent']!r}")

    status = doc.recompute(validate=validate)
    if status.get("state") != "ok":
        raise RuntimeError(f"photo CAD B-rep recompute failed: {status}")
    doc.data["maturity"] = "geometrically_valid"
    report = {
        "status": status,
        "components": len(doc.data["components"]),
        "features": len(doc.data["features"]),
        "solids": sum(v.get("valid", False) for v in doc.data["validation"].get("components", {}).values()),
        "all_valid": doc.data["validation"].get("all_valid", False),
        "assumptions": len(doc.data["assumptions"]),
        "geometry_authority": "OpenCascade B-rep",
        "sam3d_role": "visual shape hypothesis only; no mesh-to-B-rep conversion",
    }
    if not report["all_valid"]:
        raise RuntimeError(f"photo CAD validation failed: {doc.data['validation']}")
    return doc, report


def validate(doc):
    """Validate only authoritative component B-reps; no triangle-mesh checks."""
    components = {}
    for comp in doc.data.get("components", []):
        shape = doc.shapes.get(comp["output"])
        if shape is None:
            components[comp["id"]] = {"valid": False, "error": "component output is unavailable"}
            continue
        try:
            components[comp["id"]] = check_solid(shape, comp["name"], argument_analysis=True)
        except Exception as exc:
            components[comp["id"]] = {"valid": False, "error": f"{type(exc).__name__}: {exc}"[:400]}
    return {"components": components, "all_valid": bool(components) and all(x.get("valid") for x in components.values())}

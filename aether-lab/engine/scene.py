"""Scene objects turned into the light points the hologram has to rebuild."""
import numpy as np


def gear_outline(teeth=12, radius=1.5e-3, tooth_depth=0.25e-3, step=None):
    """Points along the outline of a spur gear in the xy plane (centre at origin)."""
    step = step or radius / 40
    n = max(64, int(2 * np.pi * radius / step))
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    # square-ish teeth: smooth step of a cosine
    tooth = np.clip(np.cos(teeth * t) * 3, -1, 1) * 0.5 + 0.5
    r = radius - tooth_depth + tooth_depth * tooth
    pts = np.stack([r * np.cos(t), r * np.sin(t), np.zeros_like(t)], 1)
    hub = np.linspace(0, 2 * np.pi, max(16, n // 4), endpoint=False)
    hr = radius * 0.3
    hub_pts = np.stack([hr * np.cos(hub), hr * np.sin(hub), np.zeros_like(hub)], 1)
    return np.vstack([pts, hub_pts])


def rotate(points, rx_deg=0.0, ry_deg=0.0, rz_deg=0.0):
    rx, ry, rz = np.radians([rx_deg, ry_deg, rz_deg])
    Rx = np.array([[1, 0, 0], [0, np.cos(rx), -np.sin(rx)], [0, np.sin(rx), np.cos(rx)]])
    Ry = np.array([[np.cos(ry), 0, np.sin(ry)], [0, 1, 0], [-np.sin(ry), 0, np.cos(ry)]])
    Rz = np.array([[np.cos(rz), -np.sin(rz), 0], [np.sin(rz), np.cos(rz), 0], [0, 0, 1]])
    return points @ (Rz @ Ry @ Rx).T


def place(points, x=0.0, y=0.0, z=0.05):
    return points + np.array([x, y, z])


def build(obj):
    """Scene dict -> points. obj = {type, teeth, radius, rotate:[rx,ry,rz], position:[x,y,z]}"""
    kind = obj.get("type", "gear")
    if kind == "gear":
        pts = gear_outline(obj.get("teeth", 12), obj.get("radius", 1.5e-3),
                           obj.get("tooth_depth", 0.25e-3))
    elif kind == "points":
        pts = np.asarray(obj["points"], float)
    else:
        raise ValueError(f"unknown object type {kind}")
    pts = rotate(pts, *obj.get("rotate", [0, 0, 0]))
    return place(pts, *obj.get("position", [0, 0, 0.05]))

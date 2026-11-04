"""The modelling operations named in a CAD-program component's planned method, as a CAD feature list (Loft, Split
panels, Fillet, ...). No dependencies: used by the server (feature tree, connection graph) and the CAD worker (the
drawing's parts list)."""
OPS = (("smooth_loft", "Loft"), ("loft", "Loft"), ("split_panels", "Split panels"), ("fillet_safe", "Fillet"),
       ("fillet", "Fillet"), ("chamfer", "Chamfer"), ("recess", "Recess"), ("pocket", "Pocket"), ("revolve", "Revolve"),
       ("sweep", "Sweep"), ("extrude", "Extrude"), ("mirror", "Mirror"), ("shell", "Shell"), ("cut", "Cut"),
       ("hole", "Hole"), ("union", "Union"), ("fuse", "Union"), ("box", "Box"), ("cylinder", "Cylinder"),
       ("sphere", "Sphere"), ("torus", "Torus"), ("pattern", "Pattern"), ("array", "Pattern"))


def ops_of(method):
    """Operations in the order the method text names them, each once."""
    m = (method or "").lower()
    out = []
    for _, v in sorted({(m.find(k), v) for k, v in OPS if k in m}):
        if v not in out:
            out.append(v)
    return out

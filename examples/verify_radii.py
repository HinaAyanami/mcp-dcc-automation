"""Read geometry back out of the host and prove the tapered shaft is real.

Runs inside 3ds Max (via `3dsmax_scripting__execute_python`). Prints a JSON line
so the caller can assert on numbers instead of eyeballing a screenshot:

    {"node":"Shaft","verts":520,"height":340.0,
     "bottom_r":23.0,"top_r":19.55,"ratio":0.85,
     "modifiers":["Taper","Extrude"]}

`ratio` is top radius / bottom radius: 0.85 means the taper modifier applied -15%
as intended. A screenshot cannot tell you that.
"""

from __future__ import annotations

import json

import pymxs  # noqa: F401  (bound inside the host)

rt = pymxs.runtime


def measure(node_name: str) -> dict:
    node = rt.getNodeByName(node_name)
    if node is None:
        return {"node": node_name, "error": "not found"}

    mesh = node.mesh
    count = int(mesh.numverts)
    points = []
    # `mesh.verts[i]` yields a VertexSelection wrapper, not a point.
    # `getVert` is the 1-based vertex accessor and returns an indexable Point3.
    for i in range(1, count + 1):
        v = rt.getVert(mesh, i)
        x, y, z = float(v[0]), float(v[1]), float(v[2])
        points.append((z, (x * x + y * y) ** 0.5))

    z_min = min(p[0] for p in points)
    z_max = max(p[0] for p in points)
    height = z_max - z_min

    def band(lo: float, hi: float) -> float:
        vals = [r for z, r in points if lo <= z <= hi]
        return sum(vals) / len(vals) if vals else 0.0

    bottom = band(z_min, z_min + height * 0.04)
    top = band(z_max - height * 0.04, z_max)

    # pymxs exposes the modifier stack 0-based (MaxScript is 1-based).
    mods = [str(rt.classOf(node.modifiers[i]))
            for i in range(int(node.modifiers.count))]

    return {
        "node": node_name,
        "verts": count,
        "height": round(height, 3),
        "bottom_r": round(bottom, 3),
        "top_r": round(top, 3),
        "ratio": round(top / bottom, 4) if bottom else None,
        "modifiers": mods,
        "selected": bool(node.isSelected),
    }


print("RESULT " + json.dumps(measure("Shaft")))

from pymxs import runtime as rt

# ---------- 可调参数 ----------
SHAFT_H = 340.0      # 柱身高度
SHAFT_R = 24.0       # 柱身底部半径
FLUTES = 20          # 凹槽数量
TAPER = -0.15        # 柱身上收比例（负数=向上变细）
# ------------------------------

parts = []

def add(obj, name):
    obj.name = name
    parts.append(obj)
    return obj

# 1. 柱础：方形底座 + 两层圆环
add(rt.Box(length=70, width=70, height=12, pos=rt.Point3(0, 0, 0)), "Plinth")
add(rt.Torus(radius1=29, radius2=6, sides=16, segs=48, pos=rt.Point3(0, 0, 17)), "Base_Torus_Lower")
add(rt.Torus(radius1=26, radius2=4, sides=16, segs=48, pos=rt.Point3(0, 0, 27)), "Base_Torus_Upper")

# 2. 柱身：星形截面（带圆角）拉伸出凹槽，再加锥化
z0 = 30.0
star = rt.Star(radius1=SHAFT_R, radius2=SHAFT_R - 2.0, numPoints=FLUTES,
               distort=0, fillet_Radius1=1.5, fillet_Radius2=1.5,
               pos=rt.Point3(0, 0, z0))
add(star, "Shaft")
rt.addModifier(star, rt.Extrude(amount=SHAFT_H, segments=12))
rt.addModifier(star, rt.Taper(amount=TAPER, axis=2))

# 3. 柱头：颈环 + 倒锥形圆盘（echinus）+ 方形顶板（abacus）
top = z0 + SHAFT_H
add(rt.Torus(radius1=SHAFT_R * (1 + TAPER) + 1, radius2=3, sides=12, segs=48,
             pos=rt.Point3(0, 0, top + 2)), "Neck_Ring")
add(rt.Cone(radius1=22, radius2=32, height=14, heightsegs=1, sides=48,
            pos=rt.Point3(0, 0, top + 5)), "Echinus")
add(rt.Box(length=76, width=76, height=12, pos=rt.Point3(0, 0, top + 19)), "Abacus")

# 4. 石材材质
mat = rt.StandardMaterial(name="Marble_Stone", diffuse=rt.Color(215, 208, 195))
for p in parts:
    p.material = mat

rt.select(parts)
rt.execute("max zoomext sel all")
rt.clearSelection()
print("Roman column created")

"""
hidraulica.py
-------------
Traduccion 1:1 de las macros VBA (.bas) entregadas por el usuario para las
centrales Ralco, Pangue y Palmucho del complejo Bio-Bio (Enel Chile).

Convenciones:
  * cota        -> [msnm]
  * volumen     -> [Mm3] (millones de m3)  (mismas unidades que Volmax de cada .bas)
  * caudal      -> [m3/s]
  * rendimiento -> [MW / (m3/s)]   (potencia / caudal)
  * potencia    -> [MW]

Se respetan EXACTAMENTE los coeficientes de los .bas.  Los rendimientos usados
por el modelo son Rendimiento_Ralco2 y Rendimiento_Pangue2 (pedido del usuario).
"""

# ----------------------------------------------------------------------------
#  RALCO
# ----------------------------------------------------------------------------
RALCO_COTA_MIN   = 598.0     # cota minima fisica
RALCO_COTA_MINOP = 692.0     # cota minima de operacion
RALCO_COTA_MAX   = 725.0     # cota maxima
RALCO_VOL_MAX    = 1173.61   # Mm3  (= Volumen_Ralco(725))
RALCO_VOL_MIN    = 0.0


def volumen_ralco(cota):
    d0 = 2560723.619;   d1 = 8418.733692
    d2 = -195.0203848;  d3 = 0.8735252846
    d4 = -0.001875571214; d5 = 0.000002182018751
    d6 = -1.329885007e-09; d7 = 3.344078254e-13
    v = (d0 + d1*cota + d2*cota**2 + d3*cota**3 + d4*cota**4
         + d5*cota**5 + d6*cota**6 + d7*cota**7)
    return max(v, 0.0)


def cota_ralco(volumen):
    d0 = 649.3302217;  d1 = 0.1676291546
    d2 = -0.0002381163325; d3 = 2.745693468e-07
    d4 = -2.11279019e-10;  d5 = 1.013856203e-13
    d6 = -2.739480172e-17; d7 = 3.177812069e-21
    d01 = 614.4210269; d11 = 1.263213202
    d21 = -0.02030322906; d31 = 0.0002388156292
    d41 = -0.000001801337494; d51 = 8.248826794e-09
    d61 = -2.079915343e-11;   d71 = 2.209057765e-14
    v = volumen
    if v <= 222.88:
        return (d01 + d11*v + d21*v**2 + d31*v**3 + d41*v**4
                + d51*v**5 + d61*v**6 + d71*v**7)
    else:
        return (d0 + d1*v + d2*v**2 + d3*v**3 + d4*v**4
                + d5*v**5 + d6*v**6 + d7*v**7)


def caudal_ralco(cota, potencia=690.0):
    a0, b0, c0 = 0.60915591, -0.39676086, 287.834523
    a1, b1, c1 = 0.611237,   -0.88114769, 633.454821
    a2, b2, c2 = 0.69919678, -1.82509381, 1283.66739
    a3, b3, c3 = 0.82912307, -2.98225016, 2038.97198
    p = potencia
    if p <= 180:
        return a0*p + b0*cota + c0
    elif p <= 410:
        return a1*p + b1*cota + c1
    elif p <= 600:
        return a2*p + b2*cota + c2
    else:
        return a3*p + b3*cota + c3


def rendimiento_ralco2(cota, potencia=690.0):
    return potencia / caudal_ralco(cota, potencia)


def qmax_ralco(cota):
    d2 = -0.001328940667; d1 = 2.893509358; d0 = -1031.266288
    return d2*cota**2 + d1*cota + d0


# ----------------------------------------------------------------------------
#  PANGUE
# ----------------------------------------------------------------------------
PANGUE_COTA_MIN = 495.0
PANGUE_COTA_MAX = 511.0
PANGUE_VOL_MAX  = 72.0
PANGUE_VOL_MIN  = 6.66


def volumen_pangue(cota):
    a, b, c = 0.0366, -32.43, 7091.6
    return a*cota**2 + b*cota + c


def cota_pangue(volumen):
    a, b, c = 0.0366, -32.43, 7091.6
    disc = abs(b**2 - 4*a*(c - volumen))
    return (-b + disc**0.5) / (2*a)


def caudal_pangue(cota, potencia=450.0):
    a0, b0, c0 = 0.81952037, -0.23239608, 154.576434
    a1, b1, c1 = 1.06496292, -1.64876731, 853.38298
    p = potencia
    if p <= 90:
        return a0*p + b0*cota + c0
    else:
        return a1*p + b1*cota + c1


def rendimiento_pangue2(cota, potencia=450.0):
    return potencia / caudal_pangue(cota, potencia)


# ----------------------------------------------------------------------------
#  PALMUCHO  (turbina el caudal ecologico de Ralco)
# ----------------------------------------------------------------------------
def rendimiento_palmucho(cota):
    return 0.0092*cota - 5.4648


def pmax_palmucho(cota):
    return 0.2481*cota - 148.1


if __name__ == "__main__":
    # chequeos rapidos
    print("Volumen_Ralco(725)  =", round(volumen_ralco(725), 2), "(Volmax=1173.61)")
    print("Volumen_Ralco(692)  =", round(volumen_ralco(692), 2))
    print("Cota_Ralco(1173.61) =", round(cota_ralco(1173.61), 3))
    print("Rend_Ralco2(725,640)=", round(rendimiento_ralco2(725, 640), 4), "MW/(m3/s)")
    print("Rend_Ralco2(692,640)=", round(rendimiento_ralco2(692, 640), 4))
    print("Volumen_Pangue(510) =", round(volumen_pangue(510), 3), "(Volmax=72)")
    print("Volumen_Pangue(507) =", round(volumen_pangue(507), 3))
    print("Cota_Pangue(71.96)  =", round(cota_pangue(volumen_pangue(510)), 3))
    print("Rend_Pangue2(510,400)=", round(rendimiento_pangue2(510, 400), 4))
    print("qmax_ralco(725)     =", round(qmax_ralco(725), 1), "m3/s")

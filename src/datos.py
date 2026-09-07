"""
datos.py
--------
Lectura de los Excel de caudales afluentes (formato Enel / CDEC) y construccion
de las series DIARIAS en orden calendario (01-ene a 31-dic) para cada año
hidrologico (= escenario).

Formato de los Excel de entrada (S0130134 = Ralco, S0130514 = C.I. Pangue):
  * Fila 7  : encabezados  AÑO | ABR1 ABR2 ABR3 ABR4 PROM | MAY1 ... | ... | MAR4 PROM
  * Filas 8+: un año hidrologico por fila (ej '60/61'), caudales medios semanales [m3/s]
  * Orden de meses en la fila: ABR MAY JUN JUL AGO SEP OCT NOV DIC ENE FEB MAR
  * Cada mes = 4 semanas + 1 PROM  (5 columnas)
"""
import numpy as np
import openpyxl

# Orden de los meses tal como vienen en el Excel (año hidrologico, parte ABR..MAR)
MESES_HIDRO = ["ABR", "MAY", "JUN", "JUL", "AGO", "SEP",
               "OCT", "NOV", "DIC", "ENE", "FEB", "MAR"]

# Orden calendario Ene..Dic y numero de dias (año NO bisiesto)
MESES_CAL = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN",
             "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]
DIAS_MES = {"ENE": 31, "FEB": 28, "MAR": 31, "ABR": 30, "MAY": 31, "JUN": 30,
            "JUL": 31, "AGO": 31, "SEP": 30, "OCT": 31, "NOV": 30, "DIC": 31}

# Reparto de dias por semana segun largo del mes  (regla del usuario)
REPARTO_SEMANAS = {31: [7, 8, 8, 8], 30: [7, 8, 7, 8], 28: [7, 7, 7, 7], 29: [7, 7, 7, 8]}


def leer_semanales(path_xlsx, fila_ini=8, fila_fin=None):
    """Devuelve dict {año: {mes: [q1,q2,q3,q4]}} con los caudales semanales."""
    wb = openpyxl.load_workbook(path_xlsx, data_only=True)
    ws = wb[wb.sheetnames[0]]
    if fila_fin is None:
        fila_fin = ws.max_row
    datos = {}
    for r in range(fila_ini, fila_fin + 1):
        anio = ws.cell(r, 1).value
        if anio is None or "/" not in str(anio):
            continue
        anio = str(anio).strip()
        mes_dict = {}
        ok = True
        for im, mes in enumerate(MESES_HIDRO):
            col0 = 2 + 5 * im          # columna de la semana 1 del mes
            semanas = []
            for k in range(4):
                v = ws.cell(r, col0 + k).value
                if v is None or not isinstance(v, (int, float)):
                    ok = False
                    break
                semanas.append(float(v))
            if not ok:
                break
            mes_dict[mes] = semanas
        if ok and len(mes_dict) == 12:
            datos[anio] = mes_dict
    return datos


def semanal_a_diario(semanas, ndias):
    """Expande 4 caudales semanales a una serie de 'ndias' dias."""
    reparto = REPARTO_SEMANAS[ndias]
    serie = []
    for q, nd in zip(semanas, reparto):
        serie.extend([q] * nd)
    return serie


def construir_series_diarias(path_xlsx):
    """
    Devuelve (anios, matriz) donde:
      anios  : lista de etiquetas de año hidrologico usados como escenarios
      matriz : ndarray [n_escenarios, 365] con el caudal diario [m3/s]
               en orden calendario 01-ene .. 31-dic.
    """
    semanal = leer_semanales(path_xlsx)
    anios = sorted(semanal.keys())
    filas = []
    for a in anios:
        serie = []
        for mes in MESES_CAL:
            serie.extend(semanal_a_diario(semanal[a][mes], DIAS_MES[mes]))
        filas.append(serie)
    return anios, np.array(filas, dtype=float)


if __name__ == "__main__":
    import sys
    p_ralco  = "/mnt/user-data/uploads/S0130134-25_26.xlsx"
    p_pangue = "/mnt/user-data/uploads/S0130514-25_26.xlsx"
    aR, R = construir_series_diarias(p_ralco)
    aP, P = construir_series_diarias(p_pangue)
    print("Ralco : escenarios =", len(aR), "  dias =", R.shape[1])
    print("Pangue: escenarios =", len(aP), "  dias =", P.shape[1])
    print("Años Ralco (primeros/ultimos):", aR[:3], "...", aR[-3:])
    print("Coinciden años:", aR == aP)
    # chequeo: promedio anual del primer y de un año humedo
    print("Q medio anual Ralco  60/61 :", round(R[0].mean(), 1), "m3/s")
    print("Q medio anual Pangue 60/61 :", round(P[0].mean(), 1), "m3/s")
    print("Suma dias (debe ser 365):", sum(DIAS_MES.values()))

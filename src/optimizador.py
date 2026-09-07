"""
optimizador.py
--------------
Modelo de optimizacion DIARIO (01-ene a 31-dic) del complejo Ralco + Pangue.

Objetivo: MINIMIZAR el vertimiento esperado como energia perdida [MWh] de
Ralco + Pangue, dado un mantenimiento de Ralco (Ralco detenido).

Un LP por escenario (año hidrologico).  Las no linealidades (rendimiento(cota),
pendiente dV/dcota para el limite de bajada de cota, y caudal maximo turbinable)
se tratan por LINEALIZACION SUCESIVA (2-3 iteraciones actualizando coeficientes).

Optimizacion de rendimiento: las matrices de restricciones A_eq y A_ub son
CONSTANTES (dependen solo del horizonte y de la mascara de riego); se construyen
una sola vez y solo se actualizan los vectores (b_eq, b_ub, bounds, costo).

Variables por dia t (T=365):
   Vr[t] Vp[t]  volumenes fin de dia [Mm3]
   qr[t] sr[t]  caudal turbinado / vertido Ralco  [m3/s]
   qp[t] sp[t]  caudal turbinado / vertido Pangue [m3/s]
Layout de x: [Vr | Vp | qr | sr | qp | sp]  (6*T)
"""
import numpy as np
from scipy.sparse import csr_matrix
from scipy.optimize import linprog
import hidraulica as H

K = 86400.0 / 1e6   # m3/s durante 1 dia -> Mm3   (=0.0864)
BIG = 1e7


class ModeloLP:
    """Estructura LP reutilizable para un horizonte T y una mascara de riego."""

    def __init__(self, T, riego_mask):
        self.T = T
        self.riego_mask = np.asarray(riego_mask, bool)
        self.iVr, self.iVp = 0, T
        self.iqr, self.isr = 2 * T, 3 * T
        self.iqp, self.isp = 4 * T, 5 * T
        self._build_Aeq()
        self._build_Aub()

    # -- balances (constantes) --
    def _build_Aeq(self):
        T = self.T
        rows, cols, data = [], [], []
        for t in range(T):
            # Ralco: Vr[t]-Vr[t-1]+K*qr+K*sr = ...
            rows += [t, t, t]; cols += [self.iVr + t, self.iqr + t, self.isr + t]; data += [1.0, K, K]
            if t > 0:
                rows.append(t); cols.append(self.iVr + t - 1); data.append(-1.0)
            # Pangue: Vp[t]-Vp[t-1]-K*qr-K*sr+K*qp+K*sp = ...
            r = T + t
            rows += [r, r, r, r, r]
            cols += [self.iVp + t, self.iqr + t, self.isr + t, self.iqp + t, self.isp + t]
            data += [1.0, -K, -K, K, K]
            if t > 0:
                rows.append(r); cols.append(self.iVp + t - 1); data.append(-1.0)
        self.Aeq = csr_matrix((data, (rows, cols)), shape=(2 * T, 6 * T))

    # -- inecuaciones (estructura constante) --
    def _build_Aub(self):
        T = self.T
        rows, cols, data = [], [], []
        # bloque 1: limite de bajada de cota Ralco  (Vr[t-1]-Vr[t] <= lim)
        for t in range(T):
            rows.append(t); cols.append(self.iVr + t); data.append(-1.0)
            if t > 0:
                rows.append(t); cols.append(self.iVr + t - 1); data.append(1.0)
        # bloque 2: riego (una fila por dia de temporada de riego):  -qr-sr <= eco-ar
        self.riego_dias = np.where(self.riego_mask)[0]
        self.fila_riego = {}
        r = T
        for t in self.riego_dias:
            rows += [r, r]; cols += [self.iqr + t, self.isr + t]; data += [-1.0, -1.0]
            self.fila_riego[t] = r
            r += 1
        self.n_ub = r
        self.Aub = csr_matrix((data, (rows, cols)), shape=(self.n_ub, 6 * T))

    # -- resolver un escenario --
    def resolver(self, ar, ap, par, mant_mask, n_iter=3):
        T = self.T
        eco = par["eco"]
        Vr_ini, Vr_min, Vr_max = par["Vr_ini"], par["Vr_min"], par["Vr_max"]
        Vp_ini, Vp_min, Vp_max = par["Vp_ini"], par["Vp_min"], par["Vp_max"]
        mant_mask = np.asarray(mant_mask, bool)

        # b_eq (constante en el escenario)
        beq = np.empty(2 * T)
        beq[:T] = K * (ar - eco); beq[0] += Vr_ini
        beq[T:] = K * (ap + eco); beq[T] += Vp_ini

        cota_r = np.full(T, H.cota_ralco(Vr_ini))
        cota_p = np.full(T, H.cota_pangue(Vp_ini))
        res_final = None

        for _ in range(n_iter):
            rend_r = np.array([H.rendimiento_ralco2(c, par["P_ralco_max"]) for c in cota_r])
            rend_p = np.array([H.rendimiento_pangue2(c, par["P_pangue_max"]) for c in cota_p])
            qr_max = np.array([H.caudal_ralco(c, par["P_ralco_max"]) for c in cota_r])
            qr_max = np.where(mant_mask, 0.0, qr_max)
            qp_max = np.array([H.caudal_pangue(c, par["P_pangue_max"]) for c in cota_p])
            qp_min = np.array([H.caudal_pangue(c, par["P_pangue_min"]) for c in cota_p])

            dVdc = np.array([max(H.volumen_ralco(c + 0.5) - H.volumen_ralco(c - 0.5), 1e-6)
                             for c in cota_r])
            lim_cm = np.where(cota_r > par["cota_thr"], par["drop_high"], par["drop_low"])
            dVdrop = dVdc * lim_cm

            # costo
            c = np.zeros(6 * T)
            c[self.isr:self.isr + T] = rend_r * 24.0
            c[self.isp:self.isp + T] = rend_p * 24.0

            # b_ub
            bub = np.empty(self.n_ub)
            bub[:T] = dVdrop; bub[0] += Vr_ini
            for t in self.riego_dias:
                bub[self.fila_riego[t]] = (eco - ar[t]) if ar[t] > eco else BIG

            # bounds
            lb = np.zeros(6 * T); ub = np.full(6 * T, np.inf)
            lb[self.iVr:self.iVr + T] = Vr_min; ub[self.iVr:self.iVr + T] = Vr_max
            lb[self.iVp:self.iVp + T] = Vp_min; ub[self.iVp:self.iVp + T] = Vp_max
            ub[self.iqr:self.iqr + T] = qr_max
            lb[self.iqp:self.iqp + T] = qp_min; ub[self.iqp:self.iqp + T] = qp_max
            bad = lb[self.iqp:self.iqp + T] > ub[self.iqp:self.iqp + T]
            lb[self.iqp:self.iqp + T] = np.where(bad, ub[self.iqp:self.iqp + T],
                                                 lb[self.iqp:self.iqp + T])
            bounds = np.column_stack([lb, ub])

            res = linprog(c, A_ub=self.Aub, b_ub=bub, A_eq=self.Aeq, b_eq=beq,
                          bounds=bounds, method="highs")
            if not res.success:
                lb[self.iqp:self.iqp + T] = 0.0   # fallback: relajar minimo Pangue
                bounds = np.column_stack([lb, ub])
                res = linprog(c, A_ub=self.Aub, b_ub=bub, A_eq=self.Aeq, b_eq=beq,
                              bounds=bounds, method="highs")
                if not res.success:
                    return None
            x = res.x
            Vr = x[self.iVr:self.iVr + T]; Vp = x[self.iVp:self.iVp + T]
            qr = x[self.iqr:self.iqr + T]; sr = x[self.isr:self.isr + T]
            qp = x[self.iqp:self.iqp + T]; sp = x[self.isp:self.isp + T]
            cota_r = np.array([H.cota_ralco(v) for v in Vr])
            cota_p = np.array([H.cota_pangue(v) for v in Vp])
            res_final = dict(Vr=Vr, Vp=Vp, qr=qr, sr=sr, qp=qp, sp=sp,
                             cota_r=cota_r, cota_p=cota_p, rend_r=rend_r, rend_p=rend_p)

        r = res_final
        ene_r = r["qr"] * r["rend_r"] * 24.0
        ene_p = r["qp"] * r["rend_p"] * 24.0
        ver_r = r["sr"] * r["rend_r"] * 24.0
        ver_p = r["sp"] * r["rend_p"] * 24.0
        r.update(dict(
            gen_ralco_MWh=ene_r.sum(), gen_pangue_MWh=ene_p.sum(),
            gen_total_MWh=ene_r.sum() + ene_p.sum(),
            vert_ralco_MWh=ver_r.sum(), vert_pangue_MWh=ver_p.sum(),
            vert_total_MWh=ver_r.sum() + ver_p.sum(),
            ene_ralco_serie=ene_r, ene_pangue_serie=ene_p,
            vert_ralco_serie=ver_r, vert_pangue_serie=ver_p,
        ))
        return r


# ---- API compatible con la version previa ----
_CACHE = {}


def optimizar_escenario(ar, ap, par, mant_mask, verbose=False):
    T = len(ar)
    key = (T, par["riego_mask"].tobytes())
    if key not in _CACHE:
        _CACHE[key] = ModeloLP(T, par["riego_mask"])
    return _CACHE[key].resolver(ar, ap, par, mant_mask, n_iter=par.get("n_iter", 3))


if __name__ == "__main__":
    import time, datos as D
    aR, R = D.construir_series_diarias("/mnt/user-data/uploads/S0130134-25_26.xlsx")
    aP, P = D.construir_series_diarias("/mnt/user-data/uploads/S0130514-25_26.xlsx")
    T = 365
    mpd = []
    for im, mes in enumerate(D.MESES_CAL):
        mpd += [im + 1] * D.DIAS_MES[mes]
    riego = np.isin(np.array(mpd), [1, 2, 3, 4])
    par = dict(eco=27.1, P_ralco_max=640., P_pangue_max=400., P_pangue_min=20.,
               drop_high=.40, drop_low=.25, cota_thr=710.,
               Vr_ini=H.volumen_ralco(725.), Vr_min=H.volumen_ralco(692.), Vr_max=H.volumen_ralco(725.),
               Vp_ini=H.volumen_pangue(510.), Vp_min=H.volumen_pangue(507.), Vp_max=H.volumen_pangue(510.),
               riego_mask=riego, n_iter=1)
    mant = np.zeros(T, bool); mant[(np.arange(99, 99 + 120)) % T] = True
    t0 = time.time()
    for s in range(66):
        optimizar_escenario(R[s], P[s], par, mant)
    print("66 escenarios 1 iter:", round(time.time() - t0, 2), "s")
    par["n_iter"] = 3
    t0 = time.time(); r = optimizar_escenario(R[0], P[0], par, mant)
    print("1 escenario 3 iter:", round(time.time() - t0, 3), "s")
    print("Gen total GWh:", round(r["gen_total_MWh"] / 1000, 1),
          " Vert Ralco GWh:", round(r["vert_ralco_MWh"] / 1000, 1),
          " Vert Pangue GWh:", round(r["vert_pangue_MWh"] / 1000, 1))

# Modelo de optimización Ralco + Pangue (v1 — sólo físico)

Encuentra la **fecha óptima de inicio del mantenimiento de Ralco** que
**minimiza el vertimiento esperado** (energía perdida, MWh) de Ralco + Pangue,
sobre 66 años hidrológicos (escenarios), y entrega los resultados en **bandas de
probabilidad de 20 %** (húmedo → seco) junto con la **evolución de la cota**.

## Estructura
```
Modelo_Ralco_Pangue/
├── Parametros_Modelo.xlsx      <- TODOS los parámetros, editables y explicados
├── datos/
│   ├── S0130134-25_26.xlsx     <- afluentes Ralco (semanales, m3/s)
│   ├── S0130514-25_26.xlsx     <- afluentes C.I. Pangue (semanales, m3/s)
│   └── *.bas.txt               <- macros originales (referencia)
├── src/
│   ├── hidraulica.py           <- fórmulas cota/volumen/rendimiento/caudal (traducción 1:1 de los .bas)
│   ├── datos.py                <- lectura Excel + expansión semana→día + escenarios
│   ├── optimizador.py          <- LP diario por escenario (linealización sucesiva)
│   ├── modelo.py               <- orquestador: barrido de fechas + bandas + gráficos
│   └── crear_parametros.py     <- (re)genera el Excel de parámetros
└── salidas/                    <- resultados (se crean al ejecutar)
```

## Cómo ejecutar
```bash
pip install numpy pandas scipy openpyxl matplotlib
python src/modelo.py            # usa Parametros_Modelo.xlsx en la raíz
```
Todo se controla desde `Parametros_Modelo.xlsx` (hoja **Parametros**). Para
cambiar los datos, reemplace los Excel de `datos/` (mismo formato) o ajuste las
rutas en el Excel de parámetros.

## Salidas (carpeta `salidas/`)
| Archivo | Contenido |
|---|---|
| `resumen_fecha_optima.csv` | Fecha óptima y KPIs por duración (120/150/180 días). |
| `barrido_fechas.csv` | Vertimiento esperado [GWh] vs día de inicio (curva completa). |
| `bandas_probabilidad.csv` | Vertimiento y generación por banda de 20 % (húmedo→seco). |
| `cota_evolucion_bandas.csv` | Cota diaria de Ralco y Pangue, promedio por banda. |
| `detalle_diario_bandas.csv` | Series diarias promedio por banda (afluente, cota, generación, vertimiento). |
| `fig_barrido_fechas.png` | Curva vertimiento vs fecha de inicio, con óptimos marcados. |
| `fig_cota_ralco_bandas.png` | Evolución de cota Ralco por banda. |

Los CSV de detalle se guardan siempre en **.csv** (compatibles con Power BI).

## Modelo (resumen técnico)
- **Un LP diario por escenario** (01-ene a 31-dic, 365 días). Variables por día:
  volumen Ralco/Pangue [Mm³] y caudales turbinado/vertido [m³/s] de cada central.
- **Objetivo:** minimizar Σ (vertido·rendimiento·24) = energía vertida [MWh] de
  Ralco + Pangue.
- **Embalses en volumen**; la cota se calcula sólo para mostrar (evita el error
  de la conversión ida-y-vuelta cota↔volumen).
- **No linealidades** (rendimiento(cota), pendiente dV/dcota para el límite de
  bajada de cota, caudal máximo) resueltas por **linealización sucesiva** (2–3
  iteraciones). Rendimientos = `Rendimiento_Ralco2` y `Rendimiento_Pangue2`.
- **Restricciones incluidas:** balance encadenado Ralco→Pangue (+ caudal
  ecológico 27,1 m³/s vía Palmucho que también llega a Pangue); límites de cota;
  bajada máx. de cota (40 cm/día sobre 710; 25 cm/día bajo 710); riego ene–abr
  (Ralco entrega ≥ afluente); Pangue no se detiene (Pₘᵢₙ); Ralco detenido en
  mantenimiento.
- **Bandas de probabilidad:** los 66 años se ordenan de húmedo a seco por
  afluente anual y se agrupan en 5 tramos (0-20 % … 80-100 %); números altos =
  más secos = menor vertimiento.

## Simplificaciones de la v1 (candidatas a mejorar en v2)
- Vertimiento de Ralco permitido sin forzar cota ≥ 708 (requiere binarias).
- Pₘᵢₙ de Ralco (100 MW) y prohibición de "arranque/parada" no forzadas
  (Ralco puede tomar 0–Pₘₐₓ; se relaja para mantener el LP).
- Rendimiento evaluado a potencia de referencia (Pₘₐₓ) por iteración.
- Año no bisiesto (365 días); mantenimiento puede cruzar el fin de año.
- Sin restricción de volumen final (el embalse no debe "volver" a 725).
.test
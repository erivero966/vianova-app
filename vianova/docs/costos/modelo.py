from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.comments import Comment

wb = Workbook()
F = "Arial"
BLUE = Font(name=F, color="0000FF"); BLK = Font(name=F); BOLD = Font(name=F, bold=True); GREEN = Font(name=F, color="008000")
HDR = Font(name=F, bold=True, color="FFFFFF"); HFILL = PatternFill("solid", fgColor="0F6B5C"); YEL = PatternFill("solid", fgColor="FFFF00")
thin = Side(style="thin", color="BBBBBB"); BOX = Border(top=thin, bottom=thin, left=thin, right=thin)
SOL = '"S/" #,##0.00;("S/" #,##0.00);-'
PCT = '0.0%;(0.0%);-'


def header(ws, row, vals):
    for i, v in enumerate(vals, 1):
        c = ws.cell(row=row, column=i, value=v); c.font = HDR; c.fill = HFILL; c.alignment = Alignment(wrap_text=True, vertical="center")


def widths(ws, ws_w):
    for k, v in ws_w.items():
        ws.column_dimensions[k].width = v


# ---------------------------------------------------------------- Supuestos
s = wb.active; s.title = "Supuestos"
s["A1"] = "Modelo de costos, beneficios, VAN y TIR · Aplicación móvil Vianova (PFC 2026)"; s["A1"].font = Font(name=F, bold=True, size=13)
s["A2"] = "Texto azul = dato de entrada editable · negro = fórmula · fondo amarillo = supuesto clave. Montos en soles (S/)."; s["A2"].font = BLK
header(s, 4, ["Parámetro", "Valor", "Fuente / justificación"])
rows = [
    ("Sueldo mensual de referencia, desarrollador junior (S/)", 2833, "Computrabajo (2026), promedio desarrollador full stack junior, Perú"),
    ("Horas por semana de jornada estándar", 48, "Jornada máxima legal en el Perú (Constitución, art. 25)"),
    ("Semanas por mes", 4.33, "52 semanas / 12 meses"),
    ("Dedicación por autor (h/semana)", 20, "Plan de recursos humanos del proyecto"),
    ("Duración del proyecto (semanas)", 14, "Cronograma del proyecto (Scrum, 7 sprints de 2 semanas)"),
    ("Número de autores", 2, "Equipo del proyecto"),
    ("Sueldo proyectado, perfil semi-senior IA/salud digital (S/ mes)", 6500, "Coderhouse (2026), referencia de mercado peruano"),
    ("Factor de atribución al proyecto", 0.20, "Supuesto del equipo: fracción del incremento salarial atribuible a las competencias del proyecto"),
    ("Tasa de descuento anual (r)", 0.10, "Tasa mínima referencial para proyectos académicos con componente social"),
    ("Tipo de cambio (S/ por USD)", 3.75, "Supuesto de referencia 2026; actualizar con el tipo de cambio SBS del día"),
]
for i, (p, v, src) in enumerate(rows, 5):
    s.cell(row=i, column=1, value=p).font = BLK
    c = s.cell(row=i, column=2, value=v); c.font = BLUE
    c.number_format = PCT if isinstance(v, float) and v < 1 else ('#,##0.00' if isinstance(v, float) else '#,##0')
    s.cell(row=i, column=3, value=src).font = BLK
for r in (12, 13):
    s.cell(row=r, column=2).fill = YEL
s["A16"] = "Costo por hora (S/)"; s["B16"] = "=B5/B7/B6"; s["B16"].number_format = SOL
s["A17"] = "Horas totales del equipo"; s["B17"] = "=B8*B9*B10"; s["B17"].number_format = "#,##0"
for r in (16, 17):
    s[f"A{r}"].font = BOLD; s[f"B{r}"].font = BLK
widths(s, {"A": 58, "B": 14, "C": 90})

# ---------------------------------------------------------------- Costos
c = wb.create_sheet("Costos")
header(c, 1, ["Ítem", "Descripción", "Cantidad", "Costo unitario (S/)", "Costo (S/)", "Fuente / justificación"])
items = [
    ("Dominio web", "Dominio .com, 1 año", 1, 60, "Adratech (2026), rango S/50–80/año"),
    ("Servidor de producción", "VPS para el ambiente de producción (meses)", 4, 80, "Plan de costos del proyecto; precio de VPS básico"),
    ("Servidor de pruebas/calidad", "VPS pequeño para el ambiente de pruebas (meses)", 4, 40, "Estimado del equipo (mitad del VPS de producción)"),
    ("Almacenamiento en la nube", "Respaldos cifrados; prohibido usar discos externos (meses)", 4, 10, "Estimado del equipo (almacenamiento de objetos de bajo volumen)"),
    ("API de modelo de lenguaje", "Consumo para pruebas del modo generativo del RAG", 1, 150, "Estimado del equipo; el modo local no tiene costo"),
    ("Componentes IoT (ESP32)", "2 placas ESP32 DevKit + sensores básicos", 1, 170, "Electromanía (2026), S/32–37 c/u + sensores"),
    ("Cuenta de desarrollador Google Play", "Pago único de USD 25 para publicar el APK", 1, "=25*Supuestos!B14", "Google Play Console: tarifa única de registro de USD 25"),
    ("Sesiones de pruebas de usuario", "Movilidad, refrigerios y conectividad (9–13 participantes)", 1, 300, "Plan de pruebas de usuario"),
    ("Documentación e impresión", "Impresión y entrega del informe final", 1, 150, "Estimado del equipo"),
]
for i, (it, d, q, u, src) in enumerate(items, 2):
    c.cell(row=i, column=1, value=it).font = BLK; c.cell(row=i, column=2, value=d).font = BLK
    c.cell(row=i, column=3, value=q).font = BLUE
    cu = c.cell(row=i, column=4, value=u); cu.font = GREEN if isinstance(u, str) else BLUE; cu.number_format = SOL
    t = c.cell(row=i, column=5, value=f"=C{i}*D{i}"); t.number_format = SOL; t.font = BLK
    c.cell(row=i, column=6, value=src).font = BLK
n = 1 + len(items)
c.cell(row=n + 1, column=4, value="Subtotal directo").font = BOLD
c.cell(row=n + 1, column=5, value=f"=SUM(E2:E{n})").number_format = SOL
c.cell(row=n + 2, column=4, value="Costo de oportunidad").font = BOLD
c.cell(row=n + 2, column=5, value="=Supuestos!B17*Supuestos!B16").number_format = SOL
c.cell(row=n + 3, column=4, value="COSTO TOTAL").font = BOLD
c.cell(row=n + 3, column=5, value=f"=E{n + 1}+E{n + 2}").number_format = SOL
c.cell(row=n + 3, column=5).font = BOLD
COST_TOTAL = f"Costos!E{n + 3}"
widths(c, {"A": 32, "B": 52, "C": 10, "D": 18, "E": 16, "F": 60})

# ---------------------------------------------------------------- Beneficios
b = wb.create_sheet("Beneficios")
header(b, 1, ["Beneficio", "Tipo", "Valor (S/)", "Fuente / justificación"])
b["A2"], b["B2"], b["C2"], b["D2"] = "Capacitación equivalente evitada", "No recurrente", "=2*1500", "Costo de cursos de sistemas de recomendación y RAG (S/1,500 por autor)"
b["A3"], b["B3"], b["C3"], b["D3"] = "Contribución académica", "No recurrente", 1500, "Valor estimado de una ponencia o publicación derivada"
b["A4"], b["B4"], b["C4"], b["D4"] = "Ahorro en licencias de software", "No recurrente", 1200, "Herramientas abiertas (FastAPI, scikit-learn, PostgreSQL) frente a equivalentes comerciales"
b["A5"], b["B5"], b["C5"] = "Subtotal no recurrente", "", "=SUM(C2:C4)"
b["A7"], b["B7"], b["C7"], b["D7"] = "Incremento salarial mensual", "Recurrente", "=Supuestos!B11-Supuestos!B5", "Diferencia entre perfil semi-senior y junior"
b["A8"], b["B8"], b["C8"] = "Incremento anual por autor", "Recurrente", "=C7*12"
b["A9"], b["B9"], b["C9"] = "Beneficio anual atribuido (equipo)", "Recurrente", "=C8*Supuestos!B12*Supuestos!B10"
for r in range(2, 10):
    if b[f"C{r}"].value is not None:
        b[f"C{r}"].number_format = SOL
        b[f"C{r}"].font = BLUE if isinstance(b[f"C{r}"].value, (int, float)) else BLK
for r in (5, 9):
    b[f"A{r}"].font = BOLD
widths(b, {"A": 38, "B": 16, "C": 16, "D": 80})

# ---------------------------------------------------------------- Flujo, VAN, TIR
f = wb.create_sheet("Flujo_VAN_TIR")
header(f, 1, ["Concepto", "Año 0", "Año 1", "Año 2", "Año 3"])
f["A2"] = "Inversión (costo total)"; f["B2"] = f"=-{COST_TOTAL}"
f["A3"] = "Beneficio recurrente"; f["B3"] = 0
for col in "CDE":
    f[f"{col}2"] = 0; f[f"{col}3"] = "=Beneficios!$C$9"
f["A4"] = "Beneficio no recurrente"; f["B4"] = 0; f["C4"] = "=Beneficios!C5"; f["D4"] = 0; f["E4"] = 0
f["A5"] = "Flujo neto"
for col in "BCDE":
    f[f"{col}5"] = f"=SUM({col}2:{col}4)"
f["A6"] = "Factor de descuento"
for i, col in enumerate("BCDE"):
    f[f"{col}6"] = f"=1/(1+Supuestos!$B$13)^{i}"; f[f"{col}6"].number_format = "0.0000"
f["A7"] = "Flujo descontado"
for col in "BCDE":
    f[f"{col}7"] = f"={col}5*{col}6"
for r in (2, 3, 4, 5, 7):
    for col in "BCDE":
        f[f"{col}{r}"].number_format = SOL
f["A9"] = "VAN (S/)"; f["B9"] = "=SUM(B7:E7)"; f["B9"].number_format = SOL
f["A10"] = "VAN con función NPV (control)"; f["B10"] = "=B5+NPV(Supuestos!B13,C5:E5)"; f["B10"].number_format = SOL
f["A11"] = "TIR"; f["B11"] = "=IRR(B5:E5)"; f["B11"].number_format = PCT
f["A12"] = "Beneficios totales (3 años)"; f["B12"] = "=Beneficios!C5+3*Beneficios!C9"; f["B12"].number_format = SOL
f["A13"] = "Relación beneficio/costo"; f["B13"] = f"=B12/{COST_TOTAL}"; f["B13"].number_format = "0.00"
f["A14"] = "ROI"; f["B14"] = f"=(B12-{COST_TOTAL})/{COST_TOTAL}"; f["B14"].number_format = PCT
f["A15"] = "Periodo de recuperación (años, interpolado)"
f["B15"] = '=IF(C5>=-B5,-B5/C5,1+(-B5-C5)/D5)'; f["B15"].number_format = "0.00"
for r in range(9, 16):
    f[f"A{r}"].font = BOLD
widths(f, {"A": 42, "B": 16, "C": 16, "D": 16, "E": 16})

# ---------------------------------------------------------------- Sensibilidad (VAN según atribución y tasa)
z = wb.create_sheet("Sensibilidad")
z["A1"] = "VAN (S/) según el factor de atribución (filas) y la tasa de descuento (columnas)"; z["A1"].font = BOLD
z["A2"] = "Cada celda recalcula el flujo de 3 años con la fórmula del VAN; los demás supuestos se toman de la hoja Supuestos."
rates = [0.08, 0.10, 0.12, 0.15, 0.20]; facts = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
z["A4"] = "Atribución \\ r"; z["A4"].font = BOLD
for j, r in enumerate(rates):
    cc = z.cell(row=4, column=2 + j, value=r); cc.number_format = PCT; cc.font = BLUE
for i, fa in enumerate(facts):
    rr = 5 + i
    cc = z.cell(row=rr, column=1, value=fa); cc.number_format = PCT; cc.font = BLUE
    for j in range(len(rates)):
        col = chr(66 + j)
        ben = f"(Beneficios!$C$8*$A{rr}*Supuestos!$B$10)"
        z.cell(row=rr, column=2 + j, value=(f"=-{COST_TOTAL}+({ben}+Beneficios!$C$5)/(1+{col}$4)"
                                            f"+{ben}/(1+{col}$4)^2+{ben}/(1+{col}$4)^3")).number_format = SOL
z["A12"] = "Atribución mínima para VAN = 0 con r de la hoja Supuestos"; z["A12"].font = BOLD
z["B12"] = (f"=({COST_TOTAL}-Beneficios!C5/(1+Supuestos!B13))/(Beneficios!C8*Supuestos!B10*"
            "(1/(1+Supuestos!B13)+1/(1+Supuestos!B13)^2+1/(1+Supuestos!B13)^3))")
z["B12"].number_format = PCT
z["A14"] = ("Lectura: el resultado depende sobre todo del factor de atribución, que es un supuesto del equipo. "
            "El proyecto sigue siendo rentable mientras la atribución supere el valor de B12.")
widths(z, {"A": 58, "B": 16, "C": 16, "D": 16, "E": 16, "F": 16})

for ws in wb.worksheets:
    for row in ws.iter_rows():
        for cell in row:
            if cell.font is None or cell.font.name != F:
                cell.font = Font(name=F, bold=cell.font.bold if cell.font else False, color=cell.font.color if cell.font else None)
wb.save("modelo_financiero_vianova.xlsx")

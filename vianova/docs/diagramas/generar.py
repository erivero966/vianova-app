"""Genera los diagramas del proyecto con Graphviz a partir del sistema real (modelos, routers y pantallas).
Uso: cd docs/diagramas && python generar.py      (requiere el ejecutable `dot`)
"""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "backend"))
os.environ.setdefault("VIANOVA_DATA_DIR", str(HERE / ".tmp"))
from app.db import Base          # noqa: E402
import app.models                 # noqa: E402,F401

FONT = "DejaVu Sans"
G = f'fontname="{FONT}"; node [fontname="{FONT}", fontsize=11]; edge [fontname="{FONT}", fontsize=9];'
C1, C2, C3, C4 = "#0f6b5c", "#e3f1ed", "#fff4e0", "#eef0ff"


def render(name, src, dpi=200):
    (HERE / f"{name}.dot").write_text(src, encoding="utf-8")
    subprocess.run(["dot", "-Tpng", f"-Gdpi={dpi}", "-o", str(HERE / f"{name}.png"), str(HERE / f"{name}.dot")], check=True)
    subprocess.run(["dot", "-Tsvg", "-o", str(HERE / f"{name}.svg"), str(HERE / f"{name}.dot")], check=True)
    print("ok", name)


# ------------------------------------------------------------------------------------------- 1. casos de uso
CU = {
    "Cuidador": [("CU01", "Crear cuenta, perfil\\ny consentimiento", "RF-01"), ("CU02", "Gestionar agenda\\nde cuidado", "RF-02"),
                 ("CU03", "Recibir\\nrecordatorios", "RF-03"), ("CU04", "Registrar síntoma\\n(voz o texto)", "RF-04"),
                 ("CU05", "Consultar\\nrecomendaciones", "RF-05"), ("CU06", "Consultar al\\nasistente (RAG)", "RF-06"),
                 ("CU07", "Ver fuente y\\ntraza", "RF-07"), ("CU08", "Valorar\\nrecomendación", "RF-08"),
                 ("CU09", "Revisar\\navisos", "RF-09"), ("CU10", "Exportar\\nresumen", "RF-10"),
                 ("CU11", "Importar datos\\nde wearable", "RF-11"), ("CU15", "Ejercer derechos\\nARCO", "RF-15")],
    "Curador": [("CU12", "Administrar corpus\\ny configuración", "RF-12")],
    "Administrador": [("CU13", "Gestionar usuarios,\\nroles y auditoría", "RF-13")],
    "Investigador": [("CU14", "Ver indicadores y\\nvalidación; exportar", "RF-14")],
}
lines = [f'digraph CU {{ rankdir=LR; {G} nodesep=0.18; ranksep=1.3; splines=true;']
for a in CU:
    lines.append(f'"{a}" [shape=none, image="", label="☺\\n{a}", fontsize=13];')
lines.append(f'subgraph cluster_s {{ label="Aplicación móvil Vianova"; style="rounded"; color="{C1}"; fontsize=14; penwidth=2;')
for a, cus in CU.items():
    for cid, txt, rf in cus:
        lines.append(f'{cid} [shape=ellipse, style=filled, fillcolor="{C2}", color="{C1}", label="{cid}: {txt}\\n({rf})", fontsize=10];')
lines.append('}')
lines += ['"Proveedor LLM\\n(opcional)" [shape=box, style="rounded,dashed", fontsize=10];',
          '"Reloj/pulsera" [shape=box, style="rounded,dashed", fontsize=10];']
for a, cus in CU.items():
    for cid, _, _ in cus:
        if a == "Cuidador":
            lines.append(f'"{a}" -> {cid} [arrowhead=none];')
        else:
            lines.append(f'{cid} -> "{a}" [arrowhead=none];')
lines += ['CU06 -> CU07 [style=dashed, label="«include»", arrowhead=vee, constraint=false];',
          'CU04 -> CU09 [style=dashed, label="«extend»", arrowhead=vee, constraint=false];',
          'CU05 -> CU08 [style=dashed, label="«extend»", arrowhead=vee, constraint=false];',
          'CU06 -> "Proveedor LLM\\n(opcional)" [arrowhead=none, style=dotted];',
          'CU11 -> "Reloj/pulsera" [arrowhead=none, style=dotted];', '}']
render("01_casos_de_uso", "\n".join(lines))

# ------------------------------------------------------------------------------------------- 2. modelo de BD (desde SQLAlchemy)
def coltype(c):
    t = str(c.type).replace("VARCHAR", "varchar").replace("INTEGER", "int").replace("DATETIME", "datetime")
    return t.replace("BOOLEAN", "bool").replace("FLOAT", "float").replace("TEXT", "text").replace("JSON", "json")


lines = [f'digraph ER {{ rankdir=TB; {G} node [shape=plain]; ranksep=0.6; nodesep=0.3; splines=spline;']
for t in Base.metadata.sorted_tables:
    rows = [f'<tr><td bgcolor="{C1}" colspan="2"><font color="white"><b>{t.name}</b></font></td></tr>']
    for c in t.columns:
        key = "PK" if c.primary_key else ("FK" if c.foreign_keys else "")
        rows.append(f'<tr><td align="left" port="{c.name}">{"<b>" if key else ""}{key + " " if key else ""}{c.name}{"</b>" if key else ""}</td>'
                    f'<td align="left"><font color="#5d6b67">{coltype(c)}</font></td></tr>')
    lines.append(f'{t.name} [label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="3">{"".join(rows)}</table>>];')
for t in Base.metadata.sorted_tables:
    for c in t.columns:
        for fk in c.foreign_keys:
            lines.append(f'{fk.column.table.name} -> {t.name} [arrowhead=crow, arrowtail=tee, dir=both, color="#5d6b67"];')
lines.append('}')
render("02_modelo_base_de_datos", "\n".join(lines), dpi=170)

# ------------------------------------------------------------------------------------------- 3. clases (dominio + servicios)
def cls(name, attrs, ops=(), color=C2):
    a = "<br/>".join(f'<font point-size="9">{x}</font>' for x in attrs) or " "
    o = "<br/>".join(f'<font point-size="9">{x}</font>' for x in ops) or " "
    return (f'{name.split("«")[0].strip().replace(" ", "_")} [shape=plain, label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="4">'
            f'<tr><td bgcolor="{color}"><b>{name}</b></td></tr><tr><td align="left" balign="left">{a}</td></tr>'
            f'<tr><td align="left" balign="left">{o}</td></tr></table>>];')


lines = [f'digraph CL {{ rankdir=TB; {G} ranksep=0.7; nodesep=0.4;',
         cls("Usuario", ["- código: str", "- correo: str", "- rol: Rol", "- activo: bool"], ["+ autenticar()"]),
         cls("Consentimiento", ["- tipo: str", "- versión: str", "- otorgado: bool"], ["+ revocar()"]),
         cls("PerfilPaciente", ["- tipoCáncer: str", "- tratamientos: list", "- movilidad: str", "- preferencia: str"]),
         cls("Tarea", ["- tipo: medicamento|cita|actividad", "- inicio: datetime", "- recurrencia: str"], ["+ ocurrencias(desde, hasta)"]),
         cls("Cumplimiento", ["- ocurrencia: datetime", "- estado: hecha|omitida"]),
         cls("RegistroCuidado", ["- síntoma: str", "- intensidad: int", "- valor: float", "- textoCifrado: str", "- canal: str"]),
         cls("Aviso", ["- regla: str", "- mensaje: str", "- revisado: bool"]),
         cls("Documento", ["- institución: str", "- versión: str", "- estado: incluido|excluido|retirado", "- criterios: dict"], ["+ fragmentar()"]),
         cls("Fragmento", ["- sección: str", "- texto: str", "- embedding: vector"]),
         cls("Retroalimentación", ["- útil: bool"]),
         cls("LecturaDispositivo", ["- métrica: str", "- valor: float", "- fecha: datetime"]),
         cls("RegistroUso «Tabla 8»", ["- tipoEvento", "- módulo", "- resultado", "- fuenteId", "- versiónCorpus"], color=C3),
         cls("Auditoría", ["- acción: str", "- detalle: str"], color=C3),
         cls("IndiceHíbrido «servicio»", ["- tfidf, embeddingsLSA"], ["+ construir()", "+ buscar(consulta, k)", "+ corregir(consulta)"], color=C4),
         cls("AsistenteRAG «servicio»", ["- τ, coberturaMínima"], ["+ preguntar(consulta): Respuesta", "- verificarAlcance()", "- generar()"], color=C4),
         cls("Recomendador «servicio»", ["- w1..w4"], ["+ recomendar(usuario, consulta)"], color=C4),
         cls("MotorAvisos «servicio»", ["- reglas.json"], ["+ evaluar(registro): Aviso[]"], color=C4),
         'Usuario -> Consentimiento [arrowhead=none, taillabel="1", headlabel="1..*"];',
         'Usuario -> PerfilPaciente [arrowtail=diamond, dir=back, taillabel="1", headlabel="1"];',
         'Usuario -> Tarea [arrowtail=diamond, dir=back, taillabel="1", headlabel="*"];',
         'Tarea -> Cumplimiento [arrowtail=diamond, dir=back, taillabel="1", headlabel="*"];',
         'Usuario -> RegistroCuidado [arrowtail=diamond, dir=back, taillabel="1", headlabel="*"];',
         'RegistroCuidado -> Aviso [arrowhead=none, taillabel="1", headlabel="0..*"];',
         'Aviso -> Documento [arrowhead=vee, label="cita"];',
         'Documento -> Fragmento [arrowtail=diamond, dir=back, taillabel="1", headlabel="1..*"];',
         'Usuario -> Retroalimentación [arrowhead=none, taillabel="1", headlabel="*"];', 'Retroalimentación -> Documento [arrowhead=vee];',
         'Usuario -> LecturaDispositivo [arrowhead=none, taillabel="1", headlabel="*"];',
         'Usuario -> RegistroUso [arrowhead=none, style=dashed, label="seudónimo"];',
         'IndiceHíbrido -> Fragmento [style=dashed, arrowhead=vee, label="indexa"];',
         'AsistenteRAG -> IndiceHíbrido [style=dashed, arrowhead=vee, label="usa"];',
         'Recomendador -> IndiceHíbrido [style=dashed, arrowhead=vee, label="usa"];',
         'MotorAvisos -> Aviso [style=dashed, arrowhead=vee, label="crea"];', '}']
render("03_diagrama_de_clases", "\n".join(lines))

# ------------------------------------------------------------------------------------------- 4. paquetes
lines = [f'digraph PK {{ rankdir=TB; {G} compound=true; node [shape=tab, style=filled, fillcolor="{C2}", color="{C1}"];',
         f'subgraph cluster_fe {{ label="frontend (React + Vite, PWA)"; style=rounded; color="{C1}";',
         'pages [label="pages\\n(15 pantallas)"]; apijs [label="api.js\\n(cliente HTTP)"]; voice [label="voice.jsx\\n(Web Speech API)"]; sw [label="sw.js + manifest\\n(PWA)"]; }',
         f'subgraph cluster_mo {{ label="mobile (Capacitor Android)"; style=rounded; color="{C1}"; android [label="android/"]; }}',
         f'subgraph cluster_be {{ label="backend (FastAPI)"; style=rounded; color="{C1}";',
         'routers [label="routers\\nauth · care · knowledge\\nresearch · admin · privacy"]; rag [label="rag\\nindex · assistant · safety\\ngenerator · corpus · text"];',
         'dominio [label="dominio\\nrecommender · alerts · nlp\\nschedule · indicators"]; seguridad [label="security · logs\\n(JWT, bcrypt, Fernet, auditoría)"];',
         'datos [label="models · db · config\\n(SQLAlchemy, ambientes)"]; ops [label="seed_ficticio · backup\\n(datos ficticios, respaldo cifrado)"]; }',
         f'subgraph cluster_q {{ label="calidad"; style=rounded; color="{C1}"; tests [label="backend/tests\\n(unit., integ., func., seg., IA)"]; pr [label="pruebas\\n(E2E, carga, usuarios)"]; ev [label="eval\\n(validación RAG)"]; }}',
         'pages -> apijs; pages -> voice; android -> pages [label="empaqueta"]; apijs -> routers [label="HTTPS/JSON", lhead=cluster_be];',
         'routers -> rag; routers -> dominio; routers -> seguridad; rag -> datos; dominio -> datos; dominio -> rag [label="índice"]; seguridad -> datos; ops -> datos;',
         'tests -> routers [style=dashed]; pr -> pages [style=dashed]; ev -> rag [style=dashed]; }']
render("04_diagrama_de_paquetes", "\n".join(lines))

# ------------------------------------------------------------------------------------------- 5. arquitectura lógica
lines = [f'digraph AL {{ rankdir=TB; {G} node [shape=box, style="rounded,filled", fillcolor="{C2}", color="{C1}"]; ranksep=0.5;',
         f'subgraph cluster_p {{ label="Capa de presentación"; style=filled; fillcolor="#f5f7f6"; color="{C1}";',
         'ui [label="App móvil (PWA / APK Capacitor)\\nInicio · Agenda · Registrar · Consultar · Más"]; staff [label="Módulos web del personal\\nCorpus · Usuarios · Investigación"]; }',
         f'subgraph cluster_s {{ label="Capa de servicios (API REST /api, JWT)"; style=filled; fillcolor="#f5f7f6"; color="{C1}";',
         'api [label="FastAPI: autenticación · cuidado · conocimiento · investigación · administración · privacidad"]; }',
         f'subgraph cluster_d {{ label="Capa de dominio"; style=filled; fillcolor="#f5f7f6"; color="{C1}";',
         'rec [label="Recomendador híbrido\\nw1·sem + w2·ctx + w3·reg + w4·pref"]; ragn [label="Flujo RAG\\nalcance → recuperación → τ → generación → fuentes"];',
         'av [label="Motor de avisos\\n(reglas documentadas)"]; nlp [label="Interpretación de\\nvoz/texto"]; ind [label="Indicadores y\\nregistros (Tabla 8)"]; }',
         f'subgraph cluster_r {{ label="Capa de datos y conocimiento"; style=filled; fillcolor="#f5f7f6"; color="{C1}";',
         'bd [shape=cylinder, label="Base de datos\\n(PostgreSQL / SQLite)"]; idx [shape=cylinder, label="Índice híbrido\\nTF-IDF + embeddings"]; corp [shape=folder, label="Corpus curado\\n(guías oncológicas)"]; reg [shape=note, label="rules.json"]; }',
         'llm [label="Proveedor LLM\\n(opcional, solo fragmentos)", style="rounded,dashed"]; wear [label="Archivo de wearable\\n(JSON/CSV)", style="rounded,dashed"];',
         'ui -> api; staff -> api; api -> rec; api -> ragn; api -> av; api -> nlp; api -> ind; rec -> idx; ragn -> idx; ragn -> llm [style=dashed];',
         'av -> reg; idx -> corp; rec -> bd; av -> bd; ind -> bd; nlp -> bd [style=invis]; wear -> api [style=dashed]; }']
render("05_arquitectura_logica", "\n".join(lines))

# ------------------------------------------------------------------------------------------- 6. arquitectura física y ambientes
lines = [f'digraph AF {{ rankdir=LR; {G} node [shape=box3d, style=filled, fillcolor="{C2}", color="{C1}"]; ranksep=0.8; nodesep=0.3;',
         'cel [label="Celular del cuidador\\nAndroid / iOS\\nPWA o APK"]; pc [label="PC del personal\\nnavegador"];',
         f'subgraph cluster_prod {{ label="Ambiente de PRODUCCIÓN (datos reales)"; style="rounded,filled"; fillcolor="#e6f4ea"; color="{C1}";',
         'rp [label="Proxy HTTPS\\n(TLS 1.2+)"]; app [label="Contenedor Docker\\nuvicorn + FastAPI\\n+ app web compilada"]; pg [shape=cylinder, label="PostgreSQL\\n(cifrado en reposo)"]; sec [shape=note, label="Gestor de secretos\\nJWT · Fernet · respaldos"]; }',
         f'subgraph cluster_qa {{ label="Ambiente de PRUEBAS / CALIDAD (datos ficticios)"; style="rounded,filled"; fillcolor="#eef0ff"; color="#3d4ab0";',
         'qa [label="Contenedor Docker\\nAPP_ENV=pruebas"]; qadb [shape=cylinder, label="BD de pruebas"]; }',
         f'subgraph cluster_dev {{ label="Ambiente de DESARROLLO (datos ficticios)"; style="rounded,filled"; fillcolor="#fff4e0"; color="#9a5b00";',
         'dev [label="PC del desarrollador\\nAPP_ENV=desarrollo"]; devdb [shape=cylinder, label="SQLite local"]; }',
         'nube [shape=folder, label="Almacenamiento en la nube\\n(respaldos cifrados)"]; usb [shape=box, style="filled,dashed", fillcolor="#fdecea", color="#b3261e", label="Disco externo / USB\\nPROHIBIDO"];',
         'llm [shape=box, style="rounded,dashed", label="API LLM (opcional)"];',
         'cel -> rp [label="HTTPS"]; pc -> rp [label="HTTPS"]; rp -> app; app -> pg; app -> sec [style=dotted]; app -> llm [style=dashed, label="HTTPS"];',
         'qa -> qadb; dev -> devdb; pg -> nube [label="backup.py\\ncifrado"]; pg -> usb [color="#b3261e", style=dashed, label="✗", fontcolor="#b3261e"];',
         'pg -> qadb [color="#b3261e", style=dashed, label="✗ sin copia\\nentre ambientes", fontcolor="#b3261e"]; }']
render("06_arquitectura_fisica_ambientes", "\n".join(lines))

# ------------------------------------------------------------------------------------------- 7. estados
lines = [f'digraph ST {{ rankdir=LR; {G} node [shape=box, style="rounded,filled", fillcolor="{C2}", color="{C1}"];',
         f'subgraph cluster_t {{ label="Ocurrencia de una tarea (RF-02, RF-03)"; style=rounded; color="{C1}";',
         'i1 [shape=circle, label="", width=0.2, style=filled, fillcolor=black]; pend [label="Pendiente"]; recd [label="Recordatorio\\nemitido"]; hecha [label="Hecha"]; venc [label="Vencida"]; omit [label="Omitida"];',
         'f1 [shape=doublecircle, label="", width=0.15, style=filled, fillcolor=black];',
         'i1 -> pend; pend -> recd [label="llega la hora"]; recd -> hecha [label="«Hecho»"]; pend -> hecha [label="«Hecho»"]; recd -> venc [label="pasa la\\ntolerancia"];',
         'venc -> hecha [label="«Hecho»\\n(fuera de tiempo)"]; venc -> omit [label="«No se hizo»"]; hecha -> f1; omit -> f1; }',
         f'subgraph cluster_d {{ label="Documento del corpus (RF-12)"; style=rounded; color="{C1}";',
         'i2 [shape=circle, label="", width=0.2, style=filled, fillcolor=black]; ficha [label="En curaduría\\n(ficha)"]; inc [label="Incluido\\n(indexado)"]; exc [label="Excluido"]; ret [label="Retirado"];',
         'i2 -> ficha [label="carga"]; ficha -> inc [label="cumple criterios"]; ficha -> exc [label="no cumple"]; inc -> ret [label="obsoleto\\n(+ motivo)"]; inc -> inc [label="nueva versión\\n/ reindexar"];',
         'ret -> inc [label="reincorporar"]; exc -> inc [label="corrige"]; }}',
         ]
lines[-1] = lines[-1][:-1]
lines.append('}')
render("07_diagrama_de_estados", "\n".join(lines))

# ------------------------------------------------------------------------------------------- 8. colaboración (consulta RAG)
lines = [f'digraph CO {{ rankdir=LR; {G} node [shape=box, style="filled", fillcolor="{C2}", color="{C1}"]; nodesep=0.6; ranksep=0.9;',
         'c [label=":Cuidador", shape=box]; ui [label=":PantallaConsultar"]; api [label=":RouterConocimiento"]; asis [label=":AsistenteRAG"];',
         'seg [label=":FiltroAlcance"]; idx [label=":ÍndiceHíbrido"]; gen [label=":Generador"]; bd [label=":Documento"]; log [label=":RegistroUso"];',
         'c -> ui [label="1: escribe o dicta la consulta"]; ui -> api [label="2: POST /api/assistant/ask"]; api -> asis [label="3: preguntar(consulta)"];',
         'asis -> seg [label="4: verificarAlcance()"]; asis -> idx [label="5: corregir() / buscar(k=5)"]; asis -> bd [label="6: cobertura y metadatos"];',
         'asis -> gen [label="7: generar(fragmentos ≥ τ)"]; api -> log [label="8: registrar evento\\n(sin contenido)"]; api -> ui [label="9: respuesta + fuentes + traza", style=dashed];',
         'ui -> c [label="10: muestra fuente y\\n«cómo se obtuvo»", style=dashed]; }']
render("08_diagrama_de_colaboracion_rag", "\n".join(lines))

# ------------------------------------------------------------------------------------------- 9. navegación
lines = [f'digraph NAV {{ rankdir=LR; {G} node [shape=box, style="rounded,filled", fillcolor="{C2}", color="{C1}", fontsize=10]; ranksep=0.6; nodesep=0.18;',
         'login [label="Ingreso / Crear cuenta\\n(RF-01)"]; perfil [label="Perfil y paciente\\n(RF-01)"];',
         f'subgraph cluster_tab {{ label="Barra inferior"; style=rounded; color="{C1}";',
         'inicio [label="Inicio"]; agenda [label="Agenda (RF-02)"]; registrar [label="Registrar (RF-04)"]; consultar [label="Consultar (RF-06)"]; mas [label="Más"]; }',
         'doc [label="Documento fuente\\n+ traza (RF-07)"]; recs [label="Recomendaciones\\n(RF-05, RF-08)"]; avisos [label="Avisos (RF-09)"]; record [label="Recordatorios (RF-03)"];',
         'resumen [label="Resumen (RF-10)"]; disp [label="Dispositivos (RF-11)"]; priv [label="Privacidad (RF-15)"];',
         f'subgraph cluster_staff {{ label="Personal (web)"; style=rounded; color="#3d4ab0"; corpus [label="Corpus (RF-12)"]; conf [label="Configuración (RF-12)"]; users [label="Usuarios y roles (RF-13)"]; inv [label="Investigación (RF-14)"]; val [label="Validación (RF-14)"]; }}',
         'login -> perfil [label="1.ª vez"]; login -> inicio; login -> corpus [label="curador"]; login -> users [label="admin"]; login -> inv [label="investigador"];',
         'inicio -> recs; inicio -> avisos; inicio -> registrar; inicio -> consultar; consultar -> doc; recs -> doc; registrar -> avisos [label="si hay aviso"];',
         'mas -> recs; mas -> avisos; mas -> record; mas -> resumen; mas -> disp; mas -> perfil; mas -> priv; corpus -> conf; inv -> val; users -> conf; }']
render("09_mapa_de_navegacion", "\n".join(lines))

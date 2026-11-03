"""Generador de DATOS FICTICIOS para los ambientes de desarrollo y pruebas (política de seguridad de la información).

Durante el desarrollo y las pruebas nunca se usan datos reales de cuidadores ni de pacientes. Este script crea
cuidadores ficticios (nombres inventados, correos @ficticio.pe) con perfil, tareas, cumplimientos, síntomas,
avisos y registros de uso, para probar el sistema con volumen realista.

Uso:
    APP_ENV=desarrollo python seed_ficticio.py --n 20 --dias 21
    APP_ENV=pruebas    python seed_ficticio.py --n 200 --dias 30 --semilla 7
Se niega a ejecutarse con APP_ENV=produccion.
"""
import argparse
import random
from datetime import timedelta

from app import config

if config.IS_PRODUCTION:
    raise SystemExit("seed_ficticio.py está bloqueado en producción: en producción solo existen datos reales "
                     "registrados por los propios usuarios.")

from app.main import init_db                       # noqa: E402
from app.db import SessionLocal                    # noqa: E402
from app.models import User, PatientProfile, Consent, Task, TaskCompletion, CareEvent  # noqa: E402
from app.security import hash_password, encrypt    # noqa: E402
from app.logs import log_event                     # noqa: E402
from app.schedule import occurrences               # noqa: E402
from app.timeutil import now                       # noqa: E402
from app import alerts                             # noqa: E402

NOMBRES = ["Lucía", "Mario", "Carmen", "Jorge", "Elena", "Raúl", "Teresa", "Hugo", "Patricia", "Víctor", "Sonia",
           "Iván", "Gloria", "Pablo", "Norma", "César", "Diana", "Félix", "Irma", "Óscar"]
APELLIDOS = ["Quispe", "Huamán", "Condori", "Flores", "Rojas", "Chávez", "Torres", "Vargas", "Ramos", "Salas",
             "Pari", "Ccama", "Zúñiga", "Paredes", "Linares"]
PARENTESCO = ["hija", "hijo", "esposa", "esposo", "hermana", "nieta", "sobrino"]
CANCER = ["mama", "colon", "estómago", "próstata", "pulmón", "cuello uterino", "leucemia", "linfoma"]
TRAT = ["quimioterapia", "radioterapia", "cirugia", "inmunoterapia", "paliativo"]
MOV = ["independiente", "ayuda_parcial", "encamado"]
SINT = [("nauseas", None), ("fatiga", None), ("dolor", None), ("vomitos", None), ("fiebre", 38.4), ("mucositis", None)]
TAREAS = [("medicamento", "Medicamento para las náuseas", "cada_n_horas", 8),
          ("medicamento", "Analgésico indicado", "cada_n_horas", 12),
          ("actividad", "Caminata corta acompañada", "diaria", None),
          ("actividad", "Ejercicios de respiración", "diaria", None),
          ("cita", "Control en oncología", "unica", None)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10, help="número de cuidadores ficticios")
    ap.add_argument("--dias", type=int, default=14, help="días de historial")
    ap.add_argument("--semilla", type=int, default=2026)
    a = ap.parse_args()
    rnd = random.Random(a.semilla)
    init_db()
    db = SessionLocal()
    start = (now() - timedelta(days=a.dias)).replace(minute=0, second=0, microsecond=0)
    creados = 0
    for i in range(a.n):
        email = f"ficticio{i + 1:04d}@ficticio.pe"
        if db.query(User).filter(User.email == email).first():
            continue
        n = db.query(User).filter(User.code.like("FIC-%")).count() + 1
        u = User(code=f"FIC-{n:04d}", email=email,
                 full_name=f"{rnd.choice(NOMBRES)} {rnd.choice(APELLIDOS)} (ficticio)",
                 password_hash=hash_password("Ficticio2026!"), role="cuidador")
        db.add(u)
        db.flush()
        db.add(Consent(user_id=u.id, kind="estudio", version=config.CONSENT_VERSION))
        db.add(PatientProfile(user_id=u.id, patient_alias="familiar", relationship_to_patient=rnd.choice(PARENTESCO),
                              patient_age=rnd.randint(35, 85), cancer_type=rnd.choice(CANCER),
                              treatments=rnd.sample(TRAT, rnd.randint(1, 2)), mobility=rnd.choice(MOV),
                              interaction_pref=rnd.choice(["texto", "voz"])))
        adherencia = rnd.uniform(0.55, 0.95)
        for kind, title, rec, every in rnd.sample(TAREAS, 3):
            t0 = start.replace(hour=rnd.choice([7, 8, 9, 17]))
            t = Task(user_id=u.id, kind=kind, title=title, start_at=t0 if rec != "unica" else now() + timedelta(days=3),
                     recurrence=rec, every_hours=every, created_at=t0 - timedelta(hours=1))
            db.add(t)
            db.flush()
            if rec == "unica":
                continue
            for occ in occurrences(t, t0, now() - timedelta(hours=1)):
                if rnd.random() > adherencia:
                    continue
                c = TaskCompletion(task_id=t.id, user_id=u.id, occurrence_at=occ,
                                   completed_at=occ + timedelta(minutes=rnd.choice([5, 20, 45, 90, 150])))
                db.add(c)
                ev = log_event(db, u, "tarea_completada", "actividades", id_recurso=f"TAR-{t.id:04d}",
                               hora_programada=occ, commit=False)
                ev.fecha_hora = c.completed_at
        for _ in range(rnd.randint(2, a.dias // 2 + 2)):
            sym, val = rnd.choice(SINT)
            e = CareEvent(user_id=u.id, kind="sintoma", symptom=sym, intensity=rnd.randint(2, 9),
                          value=val, unit="°C" if val else "", channel=rnd.choice(["texto", "seleccion", "voz"]),
                          text_enc=encrypt("registro ficticio generado automáticamente"),
                          occurred_at=now() - timedelta(days=rnd.randint(0, a.dias), hours=rnd.randint(0, 12)))
            db.add(e)
            db.flush()
            alerts.evaluate(db, e)
            ev = log_event(db, u, "registro_evento", "registro", id_recurso=f"EVT-{e.id:05d}", canal=e.channel, commit=False)
            ev.fecha_hora = e.occurred_at
        for d in range(a.dias, -1, -1):
            if rnd.random() < 0.8:
                ev = log_event(db, u, "inicio_sesion", "autenticacion", commit=False)
                ev.fecha_hora = now() - timedelta(days=d, hours=rnd.randint(1, 10))
        db.commit()
        creados += 1
    print(f"Ambiente '{config.APP_ENV}': {creados} cuidadores ficticios creados (contraseña común: Ficticio2026!).")


if __name__ == "__main__":
    main()

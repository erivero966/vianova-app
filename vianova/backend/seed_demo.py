"""Crea un cuidador de DEMOSTRACIÓN con perfil, tareas y registros de los últimos días (para presentaciones).

Uso: cd backend && python seed_demo.py      → usuario demo@vianova.local / Demo2026!
No usar en la base de datos del piloto.
"""
from datetime import timedelta
from app import config
if config.IS_PRODUCTION:
    raise SystemExit("seed_demo.py no puede ejecutarse en producción: allí solo hay datos reales.")
from app.main import init_db
from app.db import SessionLocal
from app.models import User, PatientProfile, Consent, Task, TaskCompletion, CareEvent
from app.security import hash_password, encrypt
from app.logs import log_event
from app.timeutil import now
from app import alerts

init_db()
db = SessionLocal()
if db.query(User).filter(User.email == "demo@vianova.local").first():
    print("El usuario demo ya existe: demo@vianova.local / Demo2026!")
    raise SystemExit
u = User(code="DEMO-CUI", email="demo@vianova.local", full_name="Rosa Mamani (demo)",
         password_hash=hash_password("Demo2026!"), role="cuidador")
db.add(u); db.flush()
db.add(Consent(user_id=u.id, kind="estudio", version="v1.0-2026"))
db.add(PatientProfile(user_id=u.id, patient_alias="papá", relationship_to_patient="hija", patient_age=68,
                      cancer_type="colon", treatments=["quimioterapia"], mobility="ayuda_parcial"))
t0 = (now() - timedelta(days=6)).replace(hour=8, minute=0, second=0)
med = Task(user_id=u.id, kind="medicamento", title="Medicamento para las náuseas", instructions="Según receta del oncólogo",
           start_at=t0, recurrence="cada_n_horas", every_hours=8, created_at=t0 - timedelta(hours=1))
walk = Task(user_id=u.id, kind="actividad", title="Caminata corta acompañada", start_at=t0.replace(hour=17),
            recurrence="diaria", created_at=t0 - timedelta(hours=1))
cita = Task(user_id=u.id, kind="cita", title="Control en oncología", start_at=(now() + timedelta(days=2)).replace(hour=10, minute=0, second=0),
            recurrence="unica")
db.add_all([med, walk, cita]); db.commit()
from app.schedule import occurrences
for t in (med, walk):
    for i, occ in enumerate(occurrences(t, t0, now() - timedelta(hours=2))):
        if i % 5 == 3:
            continue
        c = TaskCompletion(task_id=t.id, user_id=u.id, occurrence_at=occ, completed_at=occ + timedelta(minutes=15 + 10 * (i % 4)))
        db.add(c)
        ev = log_event(db, u, "tarea_completada", "actividades", id_recurso=f"TAR-{t.id:04d}", hora_programada=occ, commit=False)
        ev.fecha_hora = c.completed_at
db.commit()
for d, sym, inten, val in [(5, "nauseas", 5, None), (4, "fatiga", 6, None), (3, "nauseas", 3, None), (2, "dolor", 4, None), (1, "fatiga", 5, None)]:
    e = CareEvent(user_id=u.id, kind="sintoma", symptom=sym, intensity=inten, value=val, channel="seleccion",
                  text_enc=encrypt(""), occurred_at=now() - timedelta(days=d, hours=3))
    db.add(e); db.flush()
    ev = log_event(db, u, "registro_evento", "registro", id_recurso=f"EVT-{e.id:05d}", canal="seleccion", commit=False)
    ev.fecha_hora = e.occurred_at
for d in range(6, -1, -1):
    ev = log_event(db, u, "inicio_sesion", "autenticacion", commit=False)
    ev.fecha_hora = now() - timedelta(days=d, hours=4)
db.commit()
print("Listo: demo@vianova.local / Demo2026!")

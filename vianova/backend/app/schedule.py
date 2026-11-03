"""Generación de ocurrencias de tareas recurrentes."""
from datetime import datetime, timedelta
from .models import Task


def occurrences(task: Task, start: datetime, end: datetime) -> list[datetime]:
    out = []
    last = min(end, task.end_date) if task.end_date else end
    if task.recurrence == "unica":
        if start <= task.start_at <= last:
            out.append(task.start_at)
    elif task.recurrence == "diaria":
        cur = task.start_at
        if cur < start:
            days = (start.date() - cur.date()).days
            cur = cur + timedelta(days=max(0, days))
            if cur < start:
                cur += timedelta(days=1)
        while cur <= last:
            out.append(cur)
            cur += timedelta(days=1)
    elif task.recurrence == "cada_n_horas" and task.every_hours:
        step = timedelta(hours=task.every_hours)
        cur = task.start_at
        if cur < start:
            n = int((start - cur) / step)
            cur = cur + step * n
            if cur < start:
                cur += step
        while cur <= last:
            out.append(cur)
            cur += step
    return out

"""Funções puras usadas pelo Handler HTTP."""

import json
from datetime import datetime, time, timedelta


def parse_alerts_minutes(header_value, default=None):
    default = default or [60, 30, 15]
    try:
        bruto = json.loads(header_value or json.dumps(default))
        if isinstance(bruto, list):
            filtrados = [int(v) for v in bruto if int(v) > 0]
            if filtrados:
                return sorted(set(filtrados), reverse=True)
    except Exception:
        pass
    return list(default)


def build_nearby_events_payload(carregar, expandir, agora, alertas_minutos):
    max_min = max(alertas_minutos)
    eventos_proximos = expandir(carregar(), agora, agora + timedelta(minutes=max_min))
    alertas_set = set(alertas_minutos)
    eventos_list = []
    for occ, evento in eventos_proximos:
        faltam = int((occ - agora).total_seconds() // 60)
        if faltam in alertas_set:
            eventos_list.append({
                "titulo": evento["titulo"],
                "minutos_restantes": faltam,
                "hora": occ.strftime("%H:%M"),
                "id": evento["id"],
            })
    return {"eventos": eventos_list}


def parse_event_form(form, agenda, parse_date, fallback_time=time(9, 0)):
    d = parse_date(form.get("date"))
    hora = form.get("time", "09:00")
    try:
        inicio = datetime.strptime(f"{d.isoformat()} {hora}", agenda.FMT)
    except ValueError:
        inicio = datetime.combine(d, fallback_time)
    dur = form.get("dur", "").strip()
    rep = form.get("repeat", "none")
    until = form.get("until", "").strip() or None
    return {
        "date": d,
        "inicio": inicio,
        "dur": int(dur) if dur.isdigit() else None,
        "titulo": form.get("titulo", "Sem título").strip() or "Sem título",
        "desc": (form.get("desc") or "").strip() or None,
        "repeat": None if rep == "none" else rep,
        "until": until,
    }


def merge_event_update(evento, form, agenda, parse_date, fallback_time=time(9, 0)):
    d = parse_date(form.get("date"))
    hora = form.get("time", "09:00")
    try:
        inicio = datetime.strptime(f"{d.isoformat()} {hora}", agenda.FMT)
    except ValueError:
        inicio = datetime.combine(d, fallback_time)

    evento["titulo"] = form.get("titulo", "").strip() or evento["titulo"]
    evento["inicio"] = inicio.strftime(agenda.FMT)
    evento["dur"] = int(form.get("dur", "").strip()) if form.get("dur", "").strip().isdigit() else None
    evento["desc"] = (form.get("desc") or "").strip() or None
    evento["repeat"] = None if form.get("repeat", "none") == "none" else form.get("repeat", "none")
    evento["until"] = form.get("until", "").strip() or None

    status = form.get("status", "").strip()
    if status == "concluido":
        evento["concluido"] = True
        evento["cancelado"] = False
    elif status == "cancelado":
        evento["cancelado"] = True
        evento["concluido"] = False
    elif status == "":
        evento["concluido"] = False
        evento["cancelado"] = False

    return evento


def import_events(existing_events, incoming_events):
    eventos_atuais = list(existing_events)
    max_id = max((e["id"] for e in eventos_atuais), default=0)
    count = 0

    for ev in incoming_events:
        if "id" not in ev:
            continue
        if any(e["id"] == ev["id"] for e in eventos_atuais):
            continue
        if ev["id"] > max_id:
            max_id = ev["id"]
        eventos_atuais.append(ev)
        count += 1

    return eventos_atuais, count
#!/usr/bin/env python3
"""Agenda de eventos simples via linha de comando.

Comandos:
  new    cria um evento (com recorrencia opcional)
  edit   edita campos de um evento existente
  list   lista eventos (dia atual, data informada, ou proximas N horas)
  alerts mostra eventos que iniciam nos proximos 30 minutos
  watch  monitora e avisa (com beep) eventos que iniciam em 30 minutos
  rm     remove um evento pelo id

Exemplos:
  python agenda.py new "Reuniao" --at "2026-07-01 15:00" --dur 60 --desc "com o time"
  python agenda.py new "Standup" --at "09:00" --repeat weekdays
  python agenda.py new "Pagamento" --at "2026-07-05 10:00" --repeat monthly --until 2026-12-31
  python agenda.py edit 3 --at "16:00" --desc "remarcada"
  python agenda.py list
  python agenda.py list --date 2026-07-05
  python agenda.py list --hours 6
  python agenda.py alerts
  python agenda.py watch
  python agenda.py rm 3
"""
import argparse
import json
import sys
from datetime import datetime, time, timedelta
from pathlib import Path

# Garante saida UTF-8 mesmo em consoles Windows (cp1252).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DB = Path(__file__).with_name("eventos.json")
FMT = "%Y-%m-%d %H:%M"
DATA_FMT = "%Y-%m-%d"
ALERTA_MIN = 30
REPEATS = ("none", "daily", "weekdays", "weekly", "monthly")


# ---------------------------------------------------------------- persistencia
def carregar():
    if DB.exists():
        return json.loads(DB.read_text(encoding="utf-8"))
    return []


def salvar(eventos):
    DB.write_text(json.dumps(eventos, ensure_ascii=False, indent=2), encoding="utf-8")


def proximo_id(eventos):
    return max((e["id"] for e in eventos), default=0) + 1


# --------------------------------------------------------------------- helpers
def parse_dt(texto):
    """Aceita 'YYYY-MM-DD HH:MM' ou apenas 'HH:MM' (assume hoje)."""
    texto = texto.strip()
    try:
        return datetime.strptime(texto, FMT)
    except ValueError:
        pass
    try:
        hora = datetime.strptime(texto, "%H:%M").time()
        return datetime.combine(datetime.now().date(), hora)
    except ValueError:
        sys.exit(f"Data/hora invalida: {texto!r}. Use 'YYYY-MM-DD HH:MM' ou 'HH:MM'.")


def parse_data(texto):
    try:
        return datetime.strptime(texto.strip(), DATA_FMT).date()
    except ValueError:
        sys.exit(f"Data invalida: {texto!r}. Use 'YYYY-MM-DD'.")


def evento_inicio(e):
    return datetime.strptime(e["inicio"], FMT)


def beep():
    """Emite um beep audivel (winsound no Windows, BEL nos demais)."""
    try:
        if sys.platform == "win32":
            import winsound
            winsound.Beep(880, 400)  # 880 Hz por 400 ms
        else:
            sys.stdout.write("\a")
            sys.stdout.flush()
    except Exception:
        pass


def validar_until(until_str, inicio_dt):
    """Valida se a data 'until' não é anterior à data de início do evento."""
    if until_str:
        until_date = parse_data(until_str)
        if until_date < inicio_dt.date():
            sys.exit(f"Erro: a data --until ({until_date}) não pode ser anterior à data de início ({inicio_dt.date()}).")


# ------------------------------------------------------------------ recorrencia
def ocorre_no_dia(e, dia):
    """Diz se o evento (single ou recorrente) acontece em `dia` (date)."""
    base = evento_inicio(e).date()
    if dia < base:
        return False
    if e.get("until") and dia > parse_data(e["until"]):
        return False
    if dia.isoformat() in (e.get("except") or []):
        return False  # ocorrencia removida individualmente

    rep = e.get("repeat")
    if not rep:
        return dia == base
    if rep == "daily":
        return True
    if rep == "weekdays":
        return dia.weekday() < 5
    if rep == "weekly":
        return (dia - base).days % 7 == 0
    if rep == "monthly":
        return dia.day == base.day
    return dia == base


def ocorrencias(e, wstart, wend):
    """Datetimes de inicio do evento dentro da janela [wstart, wend]."""
    hora = evento_inicio(e).time()
    out = []
    dia = wstart.date()
    while dia <= wend.date():
        if ocorre_no_dia(e, dia):
            occ = datetime.combine(dia, hora)
            if wstart <= occ <= wend:
                out.append(occ)
        dia += timedelta(days=1)
    return out


def expandir(eventos, wstart, wend):
    """Lista ordenada de (inicio, evento) na janela, expandindo recorrencias."""
    itens = [(occ, e) for e in eventos for occ in ocorrencias(e, wstart, wend)]
    itens.sort(key=lambda x: x[0])
    return itens


def formatar(e, ini):
    linha = f"  [{e['id']:>3}] {ini:%H:%M}"
    if e.get("dur"):
        fim = ini + timedelta(minutes=e["dur"])
        linha += f"-{fim:%H:%M}"
    linha += f"  {e['titulo']}"
    if e.get("repeat"):
        rep = e["repeat"]
        linha += f"  ({rep}{' ate ' + e['until'] if e.get('until') else ''})"
    if e.get("desc"):
        linha += f"  — {e['desc']}"
    return linha


# -------------------------------------------------------------------- comandos
def cmd_new(args):
    eventos = carregar()
    inicio = parse_dt(args.at)
    until = args.until
    if until:
        parse_data(until)  # valida formato
        validar_until(until, inicio)  # valida contra data de início
    evento = {
        "id": proximo_id(eventos),
        "titulo": args.titulo,
        "inicio": inicio.strftime(FMT),
        "dur": args.dur,
        "desc": args.desc,
        "repeat": None if args.repeat == "none" else args.repeat,
        "until": until,
    }
    eventos.append(evento)
    salvar(eventos)
    print(f"Evento criado: [{evento['id']}] {evento['titulo']} em {evento['inicio']}"
          + (f" (repete {evento['repeat']})" if evento["repeat"] else ""))


def cmd_edit(args):
    eventos = carregar()
    evento = next((e for e in eventos if e["id"] == args.id), None)
    if evento is None:
        sys.exit(f"Evento {args.id} nao encontrado.")

    # Determina a nova data de início (se alterada) para validação do --until
    novo_inicio = parse_dt(args.at) if args.at is not None else evento_inicio(evento)
    novo_until = args.until if args.until is not None else evento.get("until")

    # Valida --until contra a data de início (nova ou existente)
    if novo_until is not None and novo_until not in ("", "none"):
        validar_until(novo_until, novo_inicio)

    if args.titulo is not None:
        evento["titulo"] = args.titulo
    if args.at is not None:
        evento["inicio"] = novo_inicio.strftime(FMT)
    if args.dur is not None:
        evento["dur"] = None if args.dur < 0 else args.dur
    if args.desc is not None:
        evento["desc"] = args.desc or None
    if args.repeat is not None:
        evento["repeat"] = None if args.repeat == "none" else args.repeat
    if args.until is not None:
        evento["until"] = None if args.until in ("", "none") else str(parse_data(args.until))

    salvar(eventos)
    print(f"Evento {args.id} atualizado.")
    print(formatar(evento, evento_inicio(evento)))


def cmd_list(args):
    eventos = carregar()
    agora = datetime.now()

    if args.hours is not None:
        wstart, wend = agora, agora + timedelta(hours=args.hours)
        titulo = f"Proximas {args.hours}h ({agora:%d/%m %H:%M} → {wend:%d/%m %H:%M})"
    else:
        dia = parse_data(args.date) if args.date else agora.date()
        wstart = datetime.combine(dia, time.min)
        wend = datetime.combine(dia, time.max)
        titulo = f"Eventos de {dia:%d/%m/%Y}"

    itens = expandir(eventos, wstart, wend)
    print(titulo)
    if not itens:
        print("  (nenhum evento)")
    for occ, e in itens:
        print(formatar(e, occ))


def cmd_alerts(args):
    agora = datetime.now()
    janela = expandir(carregar(), agora, agora + timedelta(minutes=ALERTA_MIN))
    if not janela:
        print(f"Nenhum evento nos proximos {ALERTA_MIN} minutos.")
        return
    print(f"⏰ Eventos iniciando nos proximos {ALERTA_MIN} minutos:")
    for occ, e in janela:
        faltam = int((occ - agora).total_seconds() // 60)
        print(f"  [{e['id']}] {e['titulo']} em {faltam} min ({occ:%H:%M})")


def cmd_watch(args):
    import time as _time

    print(f"Monitorando eventos (alerta {ALERTA_MIN} min antes). Ctrl+C para sair.")
    avisados = set()
    try:
        while True:
            agora = datetime.now()
            for occ, e in expandir(carregar(), agora, agora + timedelta(minutes=ALERTA_MIN)):
                chave = (e["id"], occ.isoformat())
                if chave not in avisados:
                    faltam = int((occ - agora).total_seconds() // 60)
                    print(f"⏰ ALERTA: '{e['titulo']}' inicia em {faltam} min ({occ:%H:%M})",
                          flush=True)
                    beep()
                    avisados.add(chave)
            _time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nMonitoramento encerrado.")


def cmd_rm(args):
    eventos = carregar()
    novos = [e for e in eventos if e["id"] != args.id]
    if len(novos) == len(eventos):
        sys.exit(f"Evento {args.id} nao encontrado.")
    salvar(novos)
    print(f"Evento {args.id} removido.")


# ------------------------------------------------------------------------ main
def main():
    p = argparse.ArgumentParser(description="Agenda de eventos simples.")
    sub = p.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("new", help="cria um evento")
    n.add_argument("titulo")
    n.add_argument("--at", required=True, help="inicio: 'YYYY-MM-DD HH:MM' ou 'HH:MM'")
    n.add_argument("--dur", type=int, default=None, help="duracao em minutos")
    n.add_argument("--desc", default=None, help="descricao")
    n.add_argument("--repeat", choices=REPEATS, default="none",
                   help="recorrencia: daily, weekdays, weekly, monthly")
    n.add_argument("--until", default=None, help="repete ate 'YYYY-MM-DD' (opcional)")
    n.set_defaults(func=cmd_new)

    e = sub.add_parser("edit", help="edita um evento (so os campos informados)")
    e.add_argument("id", type=int)
    e.add_argument("--titulo", default=None)
    e.add_argument("--at", default=None, help="novo inicio")
    e.add_argument("--dur", type=int, default=None, help="duracao em min (negativo = remove)")
    e.add_argument("--desc", default=None, help="descricao (vazio = remove)")
    e.add_argument("--repeat", choices=REPEATS, default=None)
    e.add_argument("--until", default=None, help="'YYYY-MM-DD' ou 'none' para remover")
    e.set_defaults(func=cmd_edit)

    l = sub.add_parser("list", help="lista eventos")
    l.add_argument("--date", help="dia especifico 'YYYY-MM-DD'")
    l.add_argument("--hours", type=int, nargs="?", const=6,
                   help="proximas N horas (padrao 6 se sem valor)")
    l.set_defaults(func=cmd_list)

    a = sub.add_parser("alerts", help="eventos nos proximos 30 min")
    a.set_defaults(func=cmd_alerts)

    w = sub.add_parser("watch", help="monitora e avisa (beep) 30 min antes")
    w.add_argument("--interval", type=int, default=60, help="segundos entre checagens")
    w.set_defaults(func=cmd_watch)

    r = sub.add_parser("rm", help="remove um evento")
    r.add_argument("id", type=int)
    r.set_defaults(func=cmd_rm)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

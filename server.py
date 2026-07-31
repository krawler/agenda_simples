#!/usr/bin/env python3
"""Interface web (secundaria) da agenda simples.

Mini servidor em stdlib puro (http.server) que reaproveita a logica do
agenda.py. Front-end com HTMX + Tailwind + daisyUI (via CDN).

Uso:
  python server.py            # http://localhost:8000
  python server.py --port 8080

Obs.: Thymeleaf e um motor de templates Java/Spring e nao roda em Python;
por isso a pagina e servida por este mini servidor Python, mantendo HTMX,
Tailwind e daisyUI (que sao apenas front-end).
"""
import argparse
import calendar as calmod
import html
import json
import threading
from datetime import date, datetime, time, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import agenda  # reaproveita carregar/salvar/expandir/proximo_id/FMT/REPEATS/...

WEEKDAYS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]
TEMAS = ["light", "dark", "cupcake", "corporate", "emerald", "synthwave",
         "dracula", "night", "coffee", "winter"]
MESES = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
         "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


# --------------------------------------------------------------- consultas dados
def eventos_do_dia(d):
    wstart = datetime.combine(d, time.min)
    wend = datetime.combine(d, time.max)
    return agenda.expandir(agenda.carregar(), wstart, wend)


def dias_com_eventos(ano, mes):
    ultimo = calmod.monthrange(ano, mes)[1]
    wstart = datetime.combine(date(ano, mes, 1), time.min)
    wend = datetime.combine(date(ano, mes, ultimo), time.max)
    return {occ.date() for occ, _ in agenda.expandir(agenda.carregar(), wstart, wend)}


def alertas_30min():
    agora = datetime.now()
    return agenda.expandir(agenda.carregar(), agora, agora + timedelta(minutes=30))


# ------------------------------------------------------------------- renderizacao
def esc(v):
    return html.escape(str(v)) if v is not None else ""


def render_calendar(ano, mes, sel):
    hoje = date.today()
    prev_ano, prev_mes = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
    next_ano, next_mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
    com_eventos = dias_com_eventos(ano, mes)

    cabecalho = "".join(f'<div class="text-center text-xs font-semibold '
                        f'opacity-60 py-1">{d}</div>' for d in WEEKDAYS)

    semanas = calmod.Calendar(firstweekday=6).monthdayscalendar(ano, mes)
    celulas = []
    for semana in semanas:
        for dia in semana:
            if dia == 0:
                celulas.append('<div></div>')
                continue
            d = date(ano, mes, dia)
            iso = d.isoformat()
            classes = ["btn", "btn-sm", "btn-ghost", "w-full", "flex-col",
                       "gap-0", "h-12", "relative"]
            if d == sel:
                classes = ["btn", "btn-sm", "btn-primary", "w-full", "flex-col",
                           "gap-0", "h-12", "relative"]
            elif d == hoje:
                classes.append("ring ring-primary ring-1")
            ponto = ('<span class="w-1.5 h-1.5 rounded-full bg-accent absolute '
                     'bottom-1"></span>') if d in com_eventos else ""
            celulas.append(
                f'<button class="{" ".join(classes)}" '
                f'hx-get="/day?date={iso}" hx-target="#day-panel">'
                f'<span>{dia}</span>{ponto}</button>')

    return f'''<div id="calendar" class="card bg-base-100 shadow-md">
  <div class="card-body p-4">
    <div class="flex items-center justify-between mb-2">
      <button class="btn btn-sm btn-ghost"
        hx-get="/calendar?year={prev_ano}&month={prev_mes}&sel={sel.isoformat()}"
        hx-target="#calendar" hx-swap="outerHTML">‹</button>
      <h2 class="text-lg font-bold">{MESES[mes]} {ano}</h2>
      <button class="btn btn-sm btn-ghost"
        hx-get="/calendar?year={next_ano}&month={next_mes}&sel={sel.isoformat()}"
        hx-target="#calendar" hx-swap="outerHTML">›</button>
    </div>
    <div class="grid grid-cols-7 gap-1">{cabecalho}</div>
    <div class="grid grid-cols-7 gap-1 mt-1">{"".join(celulas)}</div>
  </div>
</div>'''


def render_controls():
    """Renderiza os controles (tema, botões) para ficar abaixo do calendário."""
    return f'''<div class="card bg-base-100 shadow-md p-4">
  <div class="flex flex-col sm:flex-row items-start sm:items-center gap-2 w-full">
    <select id="tema" onchange="trocarTema(this.value)"
      class="select select-bordered select-sm w-full sm:w-auto" title="Tema">
      {"".join(f'<option value="{t}">{t}</option>' for t in TEMAS)}
    </select>
    <div class="flex flex-wrap items-center gap-2 w-full sm:w-auto justify-start sm:justify-end">
      <button class="btn btn-sm btn-ghost" hx-get="/alerts" hx-target="#alerts"
        hx-swap="outerHTML">Próximo evento</button>
      <button class="btn btn-sm btn-primary" hx-post="/sync" hx-target="#sync-status"
        hx-swap="outerHTML" hx-indicator="#sync-indicator">☁ Sincronizar Google</button>
      <span id="sync-indicator" class="loading loading-spinner loading-sm htmx-indicator"></span>
    </div>
  </div>
</div>'''


def render_evento_item(occ, e):
    dur = ""
    if e.get("dur"):
        fim = occ + timedelta(minutes=e["dur"])
        dur = f"–{fim:%H:%M}"
    badges = ""
    if e.get("repeat"):
        badges += (f'<span class="badge badge-sm badge-outline">'
                   f'{esc(e["repeat"])}</span>')
    desc = (f'<div class="text-sm opacity-70">{esc(e["desc"])}</div>'
            if e.get("desc") else "")
    iso = occ.date().isoformat()
    editar = (f'hx-get="/edit?id={e["id"]}&date={iso}" '
              f'hx-target="#day-panel"')

    if e.get("repeat"):
        acoes = f'''<div class="dropdown dropdown-end">
      <button tabindex="0" class="btn btn-xs btn-ghost">⋯</button>
      <ul tabindex="0" class="dropdown-content z-10 menu p-2 shadow bg-base-100 rounded-box w-44">
        <li><a {editar}>✎ Editar série</a></li>
        <li><a hx-post="/skip?id={e["id"]}&date={iso}" hx-target="#day-panel">
          ⤵ Pular este dia</a></li>
        <li><a class="text-error"
          hx-post="/delete?id={e["id"]}&date={iso}" hx-target="#day-panel"
          hx-confirm="Remover a série inteira '{esc(e["titulo"])}'?">🗑 Remover série</a></li>
      </ul>
    </div>'''
    else:
        acoes = f'''<div class="flex gap-1">
      <button class="btn btn-xs btn-ghost" {editar}>✎</button>
      <button class="btn btn-xs btn-ghost text-error"
        hx-post="/delete?id={e["id"]}&date={iso}" hx-target="#day-panel"
        hx-confirm="Remover '{esc(e["titulo"])}'?">✕</button>
    </div>'''

    return f'''<li class="flex items-start gap-3 p-3 rounded-lg bg-base-200">
  <div class="text-primary font-mono font-semibold whitespace-nowrap">
    {occ:%H:%M}{dur}
  </div>
  <div class="flex-1">
    <div class="font-medium flex items-center gap-2">{esc(e["titulo"])} {badges}</div>
    {desc}
  </div>
  {acoes}
</li>'''


def render_edit_form(e, occ, panel_date):
    base = agenda.evento_inicio(e)
    iso = panel_date.isoformat()
    opts = "".join(
        f'<option value="{r}"{" selected" if r == (e.get("repeat") or "none") else ""}>'
        f'{"sem repetição" if r == "none" else r}</option>'
        for r in agenda.REPEATS)
    return f'''<li class="p-3 rounded-lg bg-base-200 ring ring-primary ring-1">
  <form hx-post="/update" hx-target="#day-panel" class="space-y-2">
    <input type="hidden" name="id" value="{e["id"]}">
    <input type="hidden" name="panel_date" value="{iso}">
    <input name="titulo" required value="{esc(e["titulo"])}"
      class="input input-bordered input-sm w-full">
    <div class="flex gap-2">
      <input type="date" name="date" value="{base.date().isoformat()}" required
        class="input input-bordered input-sm flex-1">
      <input type="time" name="time" value="{base:%H:%M}" required
        class="input input-bordered input-sm w-28">
    </div>
    <div class="flex gap-2">
      <input type="number" name="dur" min="1" value="{e.get('dur') or ''}"
        placeholder="min" class="input input-bordered input-sm w-24">
      <select name="repeat" class="select select-bordered select-sm flex-1">{opts}</select>
    </div>
    <input name="desc" value="{esc(e.get('desc') or '')}" placeholder="Descrição"
      class="input input-bordered input-sm w-full">
    <input type="date" name="until" value="{esc(e.get('until') or '')}"
      title="repetir até" class="input input-bordered input-sm w-full">
    <div class="flex gap-2">
      <button class="btn btn-primary btn-sm flex-1">Salvar</button>
      <button type="button" class="btn btn-ghost btn-sm"
        hx-get="/day?date={iso}" hx-target="#day-panel">Cancelar</button>
    </div>
  </form>
</li>'''


def render_day_panel(d, editando=None):
    itens = eventos_do_dia(d)
    if itens:
        lista = "<ul class='space-y-2'>" + "".join(
            render_edit_form(e, occ, d) if e["id"] == editando
            else render_evento_item(occ, e)
            for occ, e in itens) + "</ul>"
    else:
        lista = ('<div class="text-center opacity-50 py-6">Nenhum evento '
                 'neste dia.</div>')
    iso = d.isoformat()
    opts = "".join(
        f'<option value="{r}"{" selected" if r == "none" else ""}>'
        f'{"sem repetição" if r == "none" else r}</option>'
        for r in agenda.REPEATS)

    novo_evento = ""
    if editando is None:
        novo_evento = f'''<div class="divider my-2">Novo evento</div>
    <form hx-post="/event" hx-target="#day-panel" class="space-y-2">
      <input type="hidden" name="panel_date" value="{iso}">
      <input name="titulo" required placeholder="Título"
        class="input input-bordered input-sm w-full">
      <div class="flex gap-2">
        <input type="date" name="date" value="{iso}" required
          class="input input-bordered input-sm flex-1">
        <input type="time" name="time" value="09:00" required
          class="input input-bordered input-sm w-28">
        <input type="number" name="dur" min="1" placeholder="min"
          class="input input-bordered input-sm w-24" title="duração em minutos">
      </div>
      <div class="flex gap-2">
        <select name="repeat" class="select select-bordered select-sm flex-1">
          {opts}
        </select>
        <input type="date" name="until" title="repetir até (opcional)"
        class="input input-bordered input-sm w-full">
      </div>
      <input name="desc" placeholder="Descrição (opcional)"
        class="input input-bordered input-sm w-full">
      <button class="btn btn-primary btn-sm w-full">Adicionar</button>
    </form>'''

    return f'''<div id="day-panel" class="card bg-base-100 shadow-md">
  <div class="card-body p-4">
    <h2 class="text-lg font-bold">{d:%d/%m/%Y} · {WEEKDAYS[(d.weekday()+1)%7]}</h2>
    {lista}
    {novo_evento}
  </div>
</div>'''


def render_alerts_banner():
    itens = alertas_30min()
    if not itens:
        return '<div id="alerts"></div>'
    agora = datetime.now()
    linhas = "".join(
        f'<span class="badge badge-warning gap-1">⏰ {esc(e["titulo"])} '
        f'({int((occ - agora).total_seconds() // 60)} min)</span> '
        for occ, e in itens)
    return (f'<div id="alerts" class="alert alert-warning shadow-sm">'
            f'<div class="flex flex-wrap gap-2 items-center">'
            f'<span class="font-semibold">Próximos 30 min:</span>{linhas}</div></div>')


def render_google_events_list(google_events):
    """Renderiza lista de eventos do Google Calendar no estilo do cmd_alerts."""
    if not google_events:
        return '<div class="alert alert-info shadow-sm"><div class="flex items-center gap-2"><span>Nenhum evento encontrado no Google Calendar.</span></div></div>'

    agora = datetime.now()
    linhas = []
    for ge in google_events:
        start = ge['start'].get('dateTime', ge['start'].get('date'))
        try:
            if 'T' in start:
                occ = datetime.fromisoformat(start.replace('Z', '+00:00'))
            else:
                occ = datetime.fromisoformat(start + 'T00:00:00')
        except Exception:
            occ = agora

        titulo = ge.get('summary', 'Sem título')
        # Evita erro de timezone: aware só subtrai de aware; naive só de naive.
        if occ.tzinfo is None:
            referencia = agora
            occ_fmt = occ
        else:
            referencia = datetime.now(occ.tzinfo)
            occ_fmt = occ.astimezone()

        faltam = int((occ - referencia).total_seconds() // 60)
        if faltam < 0:
            faltam_str = f"iniciou há {abs(faltam)} min"
        else:
            faltam_str = f"em {faltam} min"

        linhas.append(
            f'<div class="flex items-center gap-2 p-1">'
            f'<span class="badge badge-info">{esc(titulo)}</span>'
            f'<span class="text-xs opacity-70">({faltam_str} - {occ_fmt:%d/%m %H:%M})</span>'
            f'</div>'
        )

    return f'''<div id="google-events-list" class="alert alert-info shadow-sm">
  <div class="flex items-center justify-between mb-2">
    <span class="font-semibold">Eventos do Google Calendar ({len(google_events)}):</span>
  </div>
  <div class="space-y-1 max-h-60 overflow-y-auto">
    {"".join(linhas)}
  </div>
  <button type="button" class="btn btn-xs btn-ghost btn-circle" onclick="this.closest('#google-events-list').remove()" title="Fechar">✕</button>
</div>'''


def render_sync_status(status_msg="", is_loading=False, auto_hide=False, google_events_html=""):
    """Renderiza o status da sincronização."""
    if is_loading:
        return f'''<div id="sync-status" class="alert alert-info shadow-sm">
  <div class="flex items-center gap-2">
    <span class="loading loading-spinner loading-sm"></span>
    <span>Sincronizando com Google Calendar...</span>
  </div>
</div>'''
    elif status_msg:
        alert_class = "alert-success" if "sucesso" in status_msg.lower() or "conclu" in status_msg.lower() else "alert-error"
        auto_hide_script = ''
        if auto_hide and "sucesso" in status_msg.lower():
            auto_hide_script = '''
    <script>
      setTimeout(function() {
        var el = document.getElementById('sync-status');
        if (el) el.remove();
      }, 3000);
    </script>'''
        return f'''<div id="sync-status" class="alert {alert_class} shadow-sm">
  <div class="flex items-center gap-2">
    <span>{esc(status_msg)}</span>
  </div>
</div>
{google_events_html}
{auto_hide_script}'''
    return '<div id="sync-status"></div>'


def render_page(sel):
    return f'''<!DOCTYPE html>
<html lang="pt-br" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Agenda Simples</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://cdn.jsdelivr.net/npm/daisyui@4/dist/full.min.css" rel="stylesheet">
  <script src="https://unpkg.com/htmx.org@1.9.12"></script>
  <script>
    // aplica o tema salvo antes de renderizar (evita flash)
    (function () {{
      var t = localStorage.getItem("tema");
      if (t) document.documentElement.setAttribute("data-theme", t);
    }})();
    function trocarTema(v) {{
      document.documentElement.setAttribute("data-theme", v);
      localStorage.setItem("tema", v);
    }}
    document.addEventListener("DOMContentLoaded", function () {{
      var sel = document.getElementById("tema");
      var t = localStorage.getItem("tema");
      if (sel && t) sel.value = t;
    }});
  </script>
</head>
<body class="bg-base-200 min-h-screen">
  <div class="max-w-5xl mx-auto p-4 space-y-4">
    <header class="flex items-center justify-between gap-4">
      <h1 class="text-2xl font-bold">📅 Agenda Simples</h1>
    </header>
    {render_alerts_banner()}
    {render_sync_status()}
    <div class="grid md:grid-cols-2 gap-4 items-start">
      <div class="space-y-4">
        {render_calendar(sel.year, sel.month, sel)}
        {render_controls()}
      </div>
      {render_day_panel(sel)}
    </div>
  </div>
</body>
</html>'''


# ------------------------------------------------------------------------- server
class Handler(BaseHTTPRequestHandler):
    def _send(self, corpo, status=200):
        dados = corpo.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def _parse_date(self, texto, padrao=None):
        try:
            return datetime.strptime(texto, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return padrao or date.today()

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)

        match u.path:
            case "/":
                self._send(render_page(date.today()))
            case "/day":
                d = self._parse_date(q.get("date", [""])[0])
                self._send(render_day_panel(d))
            case "/edit":
                d = self._parse_date(q.get("date", [""])[0])
                eid = int(q.get("id", ["0"])[0])
                self._send(render_day_panel(d, editando=eid))
            case "/calendar":
                try:
                    ano = int(q.get("year", [date.today().year])[0])
                    mes = int(q.get("month", [date.today().month])[0])
                    sel = self._parse_date(q.get("sel", [""])[0])
                    self._send(render_calendar(ano, mes, sel))
                except ValueError:
                    ano = date.today().year
                    mes = date.today().month
                    # Clamp month to valid range
                    mes = max(1, min(12, mes))
                    sel = self._parse_date(q.get("sel", [""])[0])
                    self._send(render_calendar(ano, mes, sel))
            case "/alerts":
                self._send(render_alerts_banner())
            case _:
                self._send("<h1>404</h1>", 404)

    def do_POST(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        tamanho = int(self.headers.get("Content-Length", 0))
        corpo = self.rfile.read(tamanho).decode("utf-8") if tamanho else ""
        form = {k: v[0] for k, v in parse_qs(corpo).items()}

        if u.path == "/event":
            self._criar_evento(form)
        elif u.path == "/update":
            self._atualizar_evento(form)
        elif u.path == "/delete":
            self._remover_evento(q)
        elif u.path == "/skip":
            self._pular_ocorrencia(q)
        elif u.path == "/sync":
            self._sincronizar_google()
        else:
            self._send("<h1>404</h1>", 404)

    def _criar_evento(self, form):
        d = self._parse_date(form.get("date"))
        hora = form.get("time", "09:00")
        try:
            inicio = datetime.strptime(f"{d.isoformat()} {hora}", agenda.FMT)
        except ValueError:
            inicio = datetime.combine(d, time(9, 0))
        dur = form.get("dur", "").strip()
        rep = form.get("repeat", "none")
        until = form.get("until", "").strip() or None

        eventos = agenda.carregar()
        eventos.append({
            "id": agenda.proximo_id(eventos),
            "titulo": form.get("titulo", "Sem título").strip() or "Sem título",
            "inicio": inicio.strftime(agenda.FMT),
            "dur": int(dur) if dur.isdigit() else None,
            "desc": (form.get("desc") or "").strip() or None,
            "repeat": None if rep == "none" else rep,
            "until": until,
        })
        agenda.salvar(eventos)
        painel = self._parse_date(form.get("panel_date")) or d
        self._responder_com_calendario(painel)

    def _atualizar_evento(self, form):
        eid = int(form.get("id", "0"))
        eventos = agenda.carregar()
        e = next((x for x in eventos if x["id"] == eid), None)
        if e is not None:
            d = self._parse_date(form.get("date"))
            hora = form.get("time", "09:00")
            try:
                inicio = datetime.strptime(f"{d.isoformat()} {hora}", agenda.FMT)
            except ValueError:
                inicio = datetime.combine(d, time(9, 0))
            dur = form.get("dur", "").strip()
            rep = form.get("repeat", "none")
            e["titulo"] = form.get("titulo", "").strip() or e["titulo"]
            e["inicio"] = inicio.strftime(agenda.FMT)
            e["dur"] = int(dur) if dur.isdigit() else None
            e["desc"] = (form.get("desc") or "").strip() or None
            e["repeat"] = None if rep == "none" else rep
            e["until"] = form.get("until", "").strip() or None
            agenda.salvar(eventos)
        self._responder_com_calendario(self._parse_date(form.get("panel_date")))

    def _remover_evento(self, q):
        eid = int(q.get("id", ["0"])[0])
        eventos = agenda.carregar()
        evento = next((x for x in eventos if x["id"] == eid), None)
        if evento and agenda.GOOGLE_AVAILABLE and evento.get("google_id"):
            # Tenta remover do Google Calendar
            try:
                agenda.delete_event_from_google(evento)
            except:
                pass
        eventos = [e for e in agenda.carregar() if e["id"] != eid]
        agenda.salvar(eventos)
        painel = self._parse_date(q.get("date", [""])[0])
        self._responder_com_calendario(painel)

    def _pular_ocorrencia(self, q):
        eid = int(q.get("id", ["0"])[0])
        dia = self._parse_date(q.get("date", [""])[0]).isoformat()
        eventos = agenda.carregar()
        e = next((x for x in eventos if x["id"] == eid), None)
        if e is not None:
            excecoes = set(e.get("except") or [])
            excecoes.add(dia)
            e["except"] = sorted(excecoes)
            agenda.salvar(eventos)
        self._responder_com_calendario(self._parse_date(q.get("date", [""])[0]))

    def _fetch_google_events(self):
        """Busca eventos do Google Calendar para exibição."""
        if not agenda.GOOGLE_AVAILABLE:
            return []
        
        try:
            service = agenda.get_google_service()
            # Busca eventos dos últimos 30 dias até 30 dias no futuro
            time_min = datetime.now() - timedelta(days=30)
            time_max = datetime.now() + timedelta(days=30)
            return agenda.get_google_events(service, time_min, time_max)
        except Exception as ex:
            print(f"Erro ao buscar eventos do Google: {ex}")
            return []

    def _sincronizar_google(self):
        """Endpoint para sincronizar com Google Calendar (síncrono)."""
        if not agenda.GOOGLE_AVAILABLE:
            self._send(render_sync_status("Bibliotecas do Google Calendar não instaladas. Execute: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client"))
            return
        
        if not agenda.GOOGLE_CREDENTIALS_FILE.exists():
            self._send(render_sync_status("Arquivo credentials.json não encontrado. Configure no Google Cloud Console."))
            return
        
        # Primeiro, busca eventos do Google para exibir
        google_events = self._fetch_google_events()
        google_events_html = render_google_events_list(google_events)
        
        # Executa sincronização de forma síncrona
        try:
            # Envia eventos locais para o Google
            agenda.sync_all_to_google()
            # Busca eventos do Google que não estão localmente
            agenda.sync_from_google()
            msg = "Sincronização concluída com sucesso!"
        except Exception as ex:
            msg = f"Erro na sincronização: {str(ex)}"
        
        # Retorna o status final com a lista de eventos do Google
        self._send(render_sync_status(msg, auto_hide=True, google_events_html=google_events_html))

    def _responder_com_calendario(self, painel):
        # painel do dia (target) + calendario via swap-oob para atualizar os pontos
        cal_html = render_calendar(painel.year, painel.month, painel)
        cal_oob = cal_html.replace('id="calendar"',
                                   'id="calendar" hx-swap-oob="true"', 1)
        self._send(render_day_panel(painel) + cal_oob)

    def log_message(self, *a):  # silencia log padrao ruidoso
        pass


def main():
    p = argparse.ArgumentParser(description="Servidor web da agenda simples.")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--host", default="0.0.0.0")
    args = p.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Agenda web em http://{args.host}:{args.port}  (Ctrl+C para sair)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")


if __name__ == "__main__":
    main()

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
ANOS_DISPONIVEIS = [2025, 2026, 2027, 2028]


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

    return f'''<div id="calendar" class="card bg-base-100 shadow-md" data-ano="{ano}" data-mes="{mes}" data-sel="{sel.isoformat()}">
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


def render_controls(ano_atual=None):
    """Renderiza os controles (tema, botões, seletor de ano) para ficar abaixo do calendário."""
    if ano_atual is None:
        ano_atual = date.today().year
    
    opts_ano = "".join(
        f'<option value="{a}"{" selected" if a == ano_atual else ""}>{a}</option>'
        for a in ANOS_DISPONIVEIS
    )
    
    return f'''<div class="card bg-base-100 shadow-md p-4">
  <div class="flex flex-col sm:flex-row items-start sm:items-center gap-2 w-full">
    <div class="flex items-center gap-2 w-full sm:w-auto justify-start sm:justify-end">
      <select id="tema" onchange="trocarTema(this.value)"
        class="select select-bordered select-sm w-full sm:w-auto" title="Tema">
        {"".join(f'<option value="{t}">{t}</option>' for t in TEMAS)}
      </select>  
      <select id="ano-calendario" onchange="trocarAnoCalendario(this.value)"
        class="select select-bordered select-sm w-auto" title="Ano do calendário">
        {opts_ano}
      </select>
      <button class="btn btn-sm btn-primary" hx-get="/alerts" hx-target="#alerts-container"
        hx-swap="innerHTML">Próx. evento</button>
      <button class="btn btn-sm btn-primary" hx-post="/sync" hx-target="#sync-status"
        hx-swap="outerHTML" hx-indicator="#sync-indicator">☁ Sinc. Google </button>
      <span id="sync-indicator" class="loading loading-bars loading-xl htmx-indicator"></span>
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
    <div class="font-medium flex items-center gap-2">{esc(e["titulo"])} {badges}{acoes}</div>
    {desc}
  </div>
</li>'''


def render_edit_form(e, occ, panel_date):
    base = agenda.evento_inicio(e)
    iso = panel_date.isoformat()
    opts = "".join(
        f'<option value="{r}"{" selected" if r == (e.get("repeat") or "none") else ""}>'
        f'{"sem repetição" if r == "none" else r}</option>'
        for r in agenda.REPEATS)
    return f'''<li class="p-3 rounded-lg bg-base-200 ring ring-primary ring-1">
  <form hx-post="/update" hx-target="#day-panel" class="space-y-2" data-duration-confirm>
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
        placeholder="min" class="input input-bordered input-sm w-24 duration-field" id="dur-edit-{e['id']}">
      <select name="repeat" class="select select-bordered select-sm flex-1">{opts}</select>
    </div>
    <input name="desc" value="{esc(e.get('desc') or '')}" placeholder="Descrição"
      class="input input-bordered input-sm w-full">
    <input type="date" name="until" value="{esc(e.get('until') or '')}"
      title="repetir até" class="input input-bordered input-sm w-full">
    <div class="flex gap-2">
      <button type="submit" class="btn btn-primary btn-sm flex-1">Salvar</button>
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
        f'<option value="{r}"{" selected" if r == "repeat" or r == "none" else ""}>'
        f'{"sem repetição" if r == "none" else r}</option>'
        for r in agenda.REPEATS)

    novo_evento = ""
    if editando is None:
        novo_evento = f'''<div class="divider my-2">Novo evento</div>
    <form hx-post="/event" hx-target="#day-panel" class="space-y-2" data-duration-confirm>
      <input type="hidden" name="panel_date" value="{iso}">
      <input name="titulo" required placeholder="Título"
        class="input input-bordered input-sm w-full">
      <div class="flex gap-2">
        <input type="date" name="date" value="{iso}" required
          class="input input-bordered input-sm flex-1">
        <input type="time" name="time" value="09:00" required
          class="input input-bordered input-sm w-28">
        <input type="number" name="dur" min="1" placeholder="min"
          class="input input-bordered input-sm w-24 duration-field" id="dur-new" title="duração em minutos">
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
      <button type="submit" class="btn btn-primary btn-sm w-full">Adicionar</button>
    </form>'''

    return f'''<div id="day-panel" class="card bg-base-100 shadow-md">
  <div class="card-body p-4">
    <h2 class="text-lg font-bold">{d:%d/%m/%Y} · {WEEKDAYS[(d.weekday()+1)%7]}</h2>
    {lista}
    {novo_evento}
  </div>
</div>'''


def render_proximos_eventos_dia(d):
    """Renderiza lista dos próximos eventos do dia com fundo amarelo (warning)."""
    itens = agenda.proximos_eventos_dia(d)
    if not itens:
        return ('<div id="proximos-eventos" class="alert alert-warning shadow-sm">'
                '<div class="flex items-center gap-2">'
                '<span class="opacity-50">Nenhum evento futuro para hoje.</span>'
                '</div></div>')
    
    linhas = "".join(
        f'<div class="flex items-center gap-2 p-1">'
        f'<span class="badge badge-primary gap-1">{esc(e["titulo"])}</span>'
        f'<span class="text-xs opacity-70">({occ:%H:%M})</span>'
        f'</div>'
        for occ, e in itens)
    
    return f'''<div id="proximos-eventos" class="alert alert-warning shadow-sm">
  <div class="flex items-center justify-between mb-2">
    <span class="font-semibold">Próximos eventos de hoje ({len(itens)}):</span>
  </div>
  <div class="space-y-1 max-h-60 overflow-y-auto">
    {linhas}
  </div>
</div>'''


def render_alerts_banner():
    """Renderiza banner de alerta para eventos nos próximos 30 min com fundo VERMELHO (error)."""
    itens = agenda.alertas_janela(30)
    if not itens:
        return '<div id="alerts-banner"></div>'
    agora = datetime.now()
    linhas = "".join(
        f'<span class="badge badge-error gap-1">⏰ {esc(e["titulo"])} '
        f'({int((occ - agora).total_seconds() // 60)} min)</span> '
        for occ, e in itens)
    return (f'<div id="alerts-banner" class="alert alert-error shadow-sm">'
            f'<div class="flex flex-wrap gap-2 items-center">'
            f'<span class="font-semibold">⚠ Eventos iniciando em 30 min:</span>{linhas}</div></div>')


def render_google_events_list(google_events, mode="importados"):
    """
    Renderiza lista de eventos do Google Calendar.
    mode="importados": Eventos vindos do Google (azul/info)
    mode="exportados": Eventos que foram sincronizados para o Google (verde/success)
    """
    if not google_events and mode == "importados":
        return f'<div class="alert alert-base-200 shadow-sm"><div class="flex items-center gap-2"><span class="opacity-50">Nenhum evento encontrado no Google Calendar.</span></div></div>'
    elif not google_events and mode == "exportados":
        return f'<div class="alert alert-base-200 shadow-sm"><div class="flex items-center gap-2"><span class="opacity-50">Nenhum evento encontrado no calendário local.</span></div></div>'
    
    agora = datetime.now()
    linhas = []
    
    # Define cores baseadas no modo
    alert_class = "alert-info" if mode == "importados" else "alert-success my-4"
    titulo_header = "Eventos Importados do Google" if mode == "importados" else "Eventos Exportados para o Google"

    for ge in google_events:
        # ge pode ser um evento do Google (dict com 'start', 'summary') ou um dict simplificado nosso
        if 'start' in ge and 'summary' in ge:
            # Evento real do Google Calendar
            start = ge['start'].get('dateTime', ge['start'].get('date'))
            titulo = ge.get('summary', 'Sem título')
        else:
            # Nosso dict simplificado (exportados)
            start = ge.get('inicio', '')
            titulo = ge.get('titulo', 'Sem título')
        
        try:
            if 'T' in start:
                occ = datetime.fromisoformat(start.replace('Z', '+00:00'))
            else:
                occ = datetime.fromisoformat(start + 'T00:00:00')
        except Exception:
            occ = agora

        if occ.tzinfo is None:
            referencia = agora
            occ_fmt = occ
        else:
            referencia = datetime.now(occ.tzinfo)
            occ_fmt = occ.astimezone()

        faltam = int((occ - referencia).total_seconds() // 60)
        if faltam < 0:
            falta_str = f"iniciou há {abs(faltam)} min"
        else:
            falta_str = f"em {faltam} min"

        # Simplified rendering for each event
        linhas.append(
            f'<div class="flex items-center gap-2">'
            f'<span class="badge badge-primary">{esc(titulo)}</span>'
            f'<span class="text-xs opacity-70">{falta_str}</span>'
            f'</div>'
        )
    
    return f'''<div id="google-events-list-{mode}" class="alert {alert_class} shadow-sm">
                <div class="flex flex-col gap-2">{titulo_header}</div>
                {"".join(linhas)}
              </div>'''


def render_sync_status(status_msg="", is_loading=False, auto_hide=False, google_events_importados=None, google_events_exportados=None):
    """Renderiza o status da sincronização e os dois quadros de eventos."""
    if is_loading:
        return f'''<div id="sync-status" class="alert alert-info shadow-sm htmx-indicator">
                    <div class="flex items-center gap-2">
                      <span class="loading loading-spinner loading-sm"></span>
                      <span>Sincronizando com Google Calendar...</span>
                    </div>
                  </div>'''
    
    html_output = []
    
    if status_msg:
        alert_class = "alert-success" if "sucesso" in status_msg.lower() or "conclu" in status_msg.lower() else "alert-error"
        auto_hide_script = ''
        if auto_hide and "sucesso" in status_msg.lower():
            auto_hide_script = '''
            <script>
              setTimeout(function() {
                document.getElementById('sync-status').style.display = 'none';
              }, 3000);
            </script>'''
        html_output.append(f'''<div id="sync-status" class="alert {alert_class} shadow-sm">
          <div class="flex items-center gap-2">
            <span class="text-lg font-semibold">{status_msg}</span>
          </div>
        </div>{auto_hide_script}''')
    else:
        html_output.append('<div id="sync-status"></div>')

    # Render imported events if provided
    if google_events_importados:
        html_output.append(render_google_events_list(google_events_importados, mode="importados"))
    # Render exported events if provided
    if google_events_exportados:
        html_output.append(render_google_events_list(google_events_exportados, mode="exportados"))

    return "".join(html_output)


# JavaScript do modal de duração - definido como string separada para evitar problemas com f-string
DURACAO_MODAL_JS = """
  <script>
    // Variável para guardar o formulário que disparou o modal...
    // (conteúdo completo omitido para brevidade)
  </script>
"""


def render_page(sel):
    calendar_html = render_calendar(sel.year, sel.month, sel)
    controls_html = render_controls(sel.year)
    day_panel_html = render_day_panel(sel)
    alerts_html = render_alerts_banner()
    proximos_html = render_proximos_eventos_dia(sel)
    sync_html = render_sync_status()
    
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
    <header class="flex items-center justify-center gap-4">
      <h1 class="text-2xl font-bold">📅 Agenda Brasileira Definitiva</h1>
    </header>
    <div id="alerts-container">
        {alerts_html}
        {proximos_html}
        <button type="button" class="btn btn-xs btn-ghost btn-circle" onclick="document.getElementById('alerts-container').style.display = 'none'" title="Fechar">✕</button>
    </div>
    <div id="sync-container">
        <div id="sync-status" class="alert alert-info shadow-sm htmx-indicator">
          <div class="flex items-center gap-2">
            <span class="loading loading-bars loading-md"></span>
            <span class="text-lg font-semibold">&nbsp;&nbsp;Sincronizando com Google Calendar...</span>
          </div>
        </div>
        {sync_html}
    </div>
    <div class="grid md:grid-cols-2 gap-4 items-start">
      <div class="space-y-4">
        {calendar_html}
        {controls_html}
      </div>
      {day_panel_html}
    </div>
  </div>

  <!-- Modal de confirmação para duração vazia -->
  <dialog id="duracao-modal" class="modal">
    <div class="modal-box">
      <h3 class="font-bold text-lg">Duração do evento</h3>
      <p class="py-4">Deseja salvar esse evento sem tempo de duração?</p>
      <div class="modal-action">
        <form method="dialog" id="duracao-modal-form">
          <button id="btn-duracao-nao" type="button" class="btn btn-ghost">Não</button>
          <button id="btn-duracao-sim" type="button" class="btn btn-primary">Sim</button>
        </form>
      </div>
    </div>
    <form method="dialog" class="modal-backdrop">
      <button>Fechar</button>
    </form>
  </dialog>

  {DURACAO_MODAL_JS}
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
                    mes = max(1, min(12, mes))
                    sel = self._parse_date(q.get("sel", [""])[0])
                    self._send(render_calendar(ano, mes, sel))
            case "/alerts":
                # Retorna tanto o banner de alerta (vermelho se eventos em 30min) 
                # quanto a lista de próximos eventos do dia (amarelo)
                d = date.today()
                alerts_banner = render_alerts_banner()
                proximos_eventos = render_proximos_eventos_dia(d)
                self._send(alerts_banner + proximos_eventos)
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

    def _sincronizar_google(self):
        
        if not agenda.GOOGLE_AVAILABLE:
            self._send(render_sync_status("Bibliotecas do Google Calendar não instaladas."))
            return
        
        if not agenda.GOOGLE_CREDENTIALS_FILE.exists():
            self._send(render_sync_status("Arquivo credentials.json não encontrado."))
            return
        
        # Executa a sincronização bidirecional e obtém os resultados detalhados
        msg, exportados, importados = agenda.sync_all_and_get_results()
        
        # Envia resposta com os dois painéis
        self._send(render_sync_status(msg, is_loading=False, auto_hide=True, 
                                     google_events_importados=importados,
                                     google_events_exportados=exportados))

    def _responder_com_calendario(self, painel):
        cal_html = render_calendar(painel.year, painel.month, painel)
        cal_oob = cal_html.replace('id="calendar"',
                                   'id="calendar" hx-swap-oob="true"', 1)
        self._send(render_day_panel(painel) + cal_oob)

    def log_message(self, *a):
        pass


def main():
    p = argparse.ArgumentParser(description="Servidor web da agenda simples.")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--host", default="127.0.0-1",
                   help="Endereço de escuta. Use 0.0.0.0 para aceitar conexões externas.")
    args = p.parse_args()
    try:
        srv = ThreadingHTTPServer((args.host, args.port), Handler)
    except PermissionError as ex:
        print(f"Erro ao abrir o servidor em {args.host}:{args.port}: {ex}")
        print("Tente usar uma porta diferente ou execute com privilégios elevados.")
        print("Para uso local, rode: python server.py --host 127.0.0.1")
        return

    print(f"Agenda web em http://{args.host}:{args.port}  (Ctrl+C para sair)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")


if __name__ == "__main__":
    main()

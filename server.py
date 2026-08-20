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
import re
import threading
import time as time_module
import os
import sys
import subprocess
import signal
from datetime import date, datetime, time, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from pathlib import Path

import agenda  # reaproveita carregar/salvar/expandir/proximo_id/FMT/REPEATS/...

WEEKDAYS = ["Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"]
TEMAS = ["light", "dark", "cupcake", "corporate", "emerald", "synthwave",
           "dracula", "night", "coffee", "winter"]
MESES = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
           "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
ANOS_DISPONIVEIS = [2025, 2026, 2027, 2028]

# Caminho para templates
TEMPLATES_DIR = Path(__file__).parent / "templates"

# Armazenar conexões SSE ativas
sse_clients = []

# Armazenar timestamps de arquivos monitoradas
file_timestamps = {}

# Flag para evitar múltiplos restarts simultâneos
restart_em_andamento = False

# Instância global do servidor para permitir shutdown coordenado.
server_instance = None

# Arquivo PID para controle do servidor em modo dev.
PID_FILE = Path(__file__).parent / ".agenda_server.pid"

# Lock para acesso thread-safe aos clientes SSE
sse_lock = threading.Lock()


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


def linkify_urls(text):
    """Converte URLs em texto para links clicáveis."""
    if not text:
        return ""
    # Regex para detectar URLs (http, https, ftp, file, mailto, etc.)
    url_pattern = re.compile(
        r'(?i)\b((?:https?://|ftp://|file://|mailto:|www\.)[^\s<>"\']+)'
    )
    
    def replace_url(match):
        url = match.group(1)
        # Se não tem protocolo, adiciona http://
        href = url if re.match(r'^[a-z]+://', url, re.I) else 'http://' + url
        return f'<a href="{esc(href)}" target="_blank" rel="noopener noreferrer" class="link link-primary underline">{esc(url)}</a>'
    
    return url_pattern.sub(replace_url, text)


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
    
    """Renderiza os controles (botões, seletor de ano) para ficar abaixo do calendário.""" 
    return f'''<div class="card bg-base-100 shadow-md p-4">
  <div class="flex flex-col sm:flex-row items-start sm:items-center gap-2 w-full">
    <div class="flex flex-col sm:flex-row items-stretch gap-2 w-full">
      <!-- Primeira linha: 2 botões -->
      <div class="flex flex-wrap gap-2 w-full">
        <button class="btn btn-sm btn-primary flex-1 min-w-[140px]" hx-get="/alerts" hx-target="#alerts-container"
          hx-swap="innerHTML">→ Próximos eventos </button>
        <button id="sync-google" class="btn btn-sm btn-primary flex-1 min-w-[140px]">☁ Sincronizar eventos </button>
      </div>
      <!-- Segunda linha: Ideias e planos + Configurações -->
      <div class="flex flex-wrap gap-2 w-full">
        <button id="ideas-plans" class="btn btn-sm btn-primary flex-1 min-w-[140px]" onclick="abrirIdeiasPlanos()">
          💡 Ideias e planos
        </button>
        <button class="btn btn-sm btn-primary flex-1 min-w-[140px]" onclick="abrirConfig()">
          ⚙️ Configurações
        </button>
      </div>
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
    desc = (f'<div class="text-sm opacity-70">{linkify_urls(e["desc"])}</div>'
            if e.get("desc") else "")
    iso = occ.date().isoformat()
    editar = (f'hx-get="/edit?id={e["id"]}&date={iso}" '
              f'hx-target="#day-panel"')

    # Indicadores de status
    status_indicador = ""
    agora = datetime.now()
    if e.get("cancelado"):
        status_indicador = '<span class="text-red-400 font-medium">(evento cancelado)</span>'
    elif e.get("concluido") and occ > agora:
        status_indicador = '<span class="text-green-700 font-medium">(evento concluído)</span>'

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
    {status_indicador}
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
    
    # Opções de status
    status_opts = ""
    current_status = ""
    if e.get("cancelado"):
        current_status = "cancelado"
    elif e.get("concluido"):
        current_status = "concluido"
    
    status_opts = ''.join([
        f'<option value=""{" selected" if current_status == "" else ""}>Status</option>',
        f'<option value="concluido"{" selected" if current_status == "concluido" else ""}>Concluído</option>',
        f'<option value="cancelado"{" selected" if current_status == "cancelado" else ""}>Cancelado</option>'
    ])

    return f'''<li class="p-3 rounded-lg bg-base-200 ring ring-primary ring-1">
  <form hx-post="/update" hx-target="#day-panel" class="space-y-2" data-duration-confirm>
    <input type="hidden" name="id" value="{e["id"]}">
    <input type="hidden" name="panel_date" value="{iso}">
    <input name="titulo" required value="{esc(e["titulo"])}"
      class="input input-bordered input-sm w-full"
      data-balloon-content="Preencha o título do evento"
      data-balloon-pos="right"
      data-balloon-class="balloon-dark">
    <div class="flex gap-2">
      <input type="date" name="date" value="{base.date().isoformat()}" required
        class="input input-bordered input-sm flex-1"
        data-balloon-content="Selecione a data do evento"
        data-balloon-pos="right"
        data-balloon-class="balloon-dark">
      <input type="time" name="time" value="{base:%H:%M}" required
        class="input input-bordered input-sm w-28"
        data-balloon-content="Defina a hora de início"
        data-balloon-pos="right"
        data-balloon-class="balloon-dark">
      <input type="number" name="dur" min="1" value="{e.get('dur') or ''}"
        placeholder="min" class="input input-bordered input-sm w-24 duration-field" id="dur-edit-{e['id']}"
        data-balloon-content="Duração em minutos"
        data-balloon-pos="right"
        data-balloon-class="balloon-dark">
    </div>
    <div class="flex grid md:grid-cols-3 gap-2">
      <select name="repeat" class="select select-bordered select-sm flex-1"
        data-balloon-content="Tipo de repetição"
        data-balloon-pos="right"
        data-balloon-class="balloon-dark">{opts}</select>
       <input type="date" name="until" value="{esc(e.get('until') or '')}"
                title="repetir até" class="input input-bordered input-sm"
                data-balloon-content="Data limite para repetição"
                data-balloon-pos="right"
                data-balloon-class="balloon-dark">
        <select name="status" class="select select-bordered select-sm flex-1"
              data-balloon-content="Status do evento"
              data-balloon-pos="right"
              data-balloon-class="balloon-dark">
              {status_opts}
            </select>  
    </div>
    <div class="flex gap-2">
      <input name="desc" value="{esc(e.get('desc') or '')}" placeholder="Descrição"
            class="input input-bordered input-sm w-full"
            data-balloon-content="Descrição opcional do evento"
            data-balloon-pos="right"
            data-balloon-class="balloon-dark">
    </div>
    <div class="flex gap-2">
      <button type="submit" class="btn btn-primary btn-sm flex-1">Salvar</button>
      <button type="button" class="btn btn-ghost btn-sm flex-1"
        hx-get="/day?date={iso}" hx-target="#day-panel">Cancelar Evento</button>
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

    # Opções de status para novo evento
    status_opts_novo = ''.join([
        '<option value="">Status</option>',
        '<option value="concluido">Concluído</option>',
        '<option value="cancelado">Cancelado</option>'
    ])

    novo_evento = ""
    if editando is None:
        novo_evento = f'''<div class="divider my-2">Novo evento</div>
    <form hx-post="/event" hx-target="#day-panel" class="space-y-2" data-duration-confirm>
      <input type="hidden" name="panel_date" value="{iso}">
      <input name="titulo" required placeholder="Título" type="text"
        class="input input-bordered input-sm w-full"
        data-balloon-content="Preencha o título do evento"
        data-balloon-pos="right"
        data-balloon-class="balloon-dark">
      <div class="flex gap-2">
        <input type="date" name="date" value="{iso}" required
          class="input input-bordered input-sm flex-1"
          data-balloon-content="Selecione a data do evento"
          data-balloon-pos="right"
          data-balloon-class="balloon-dark">
        <input type="time" name="time" value="09:00" required
          class="input input-bordered input-sm w-28"
          data-balloon-content="Defina a hora de início"
          data-balloon-pos="right"
          data-balloon-class="balloon-dark">
        <input type="number" name="dur" min="1" placeholder="min"
          class="input input-bordered input-sm w-24 duration-field" id="dur-new" title="duração em minutos"
          data-balloon-content="Duração em minutos"
          data-balloon-pos="right"
          data-balloon-class="balloon-dark">
      </div>
      <div class="flex grid md:grid-cols-3 gap-2">
        <select name="repeat" class="select select-bordered select-sm flex-1"
          data-balloon-content="Tipo de repetição"
          data-balloon-pos="right"
          data-balloon-class="balloon-dark">
          {opts}
        </select>
        <input type="date" name="until" title="repetir até (opcional)"
          class="input input-bordered input-sm w-full"
          data-balloon-content="Data limite para repetição (opcional)"
          data-balloon-pos="right"
          data-balloon-class="balloon-dark">
        <select name="status" class="select select-bordered select-sm flex-1"
                data-balloon-content="Status do evento"
                data-balloon-pos="right"
                data-balloon-class="balloon-dark">
                {status_opts_novo}
              </select>
      </div>
      <input name="desc" placeholder="Descrição (opcional)"
        class="input input-bordered input-sm w-full"
        data-balloon-content="Descrição opcional do evento"
        data-balloon-pos="right"
        data-balloon-class="balloon-dark">
      <div class="flex gap-2">  
        <button type="submit" class="btn btn-primary btn-sm flex-1">Adicionar</button>
        <button type="button" class="btn btn-ghost btn-sm bg-gray-100 flex-1">Cancelar</button>
      </div>  
    </form>'''

    return f'''<div id="day-panel" class="card bg-base-100 shadow-md">
  <div class="card-body p-4">
    <h2 class="text-lg font-bold">{d:%d/%m/%Y} · {WEEKDAYS[(d.weekday()+1)%7]}</h2>
    {lista}
    {novo_evento}
  </div>
</div>'''


def render_proximos_eventos_dia(d):
    """Renderiza lista dos próximos eventos do dia com fundo amarelo (warning).
    Se não houver eventos futuros para hoje, mostra os eventos de amanhã."""
    hoje = date.today()
    itens_hoje = agenda.proximos_eventos_dia(d)
    
    # Se há eventos para hoje (ou para o dia selecionado), mostra apenas eles
    if itens_hoje:
        linhas = "".join(
            f'<div class="flex items-center gap-2 p-1">'
            f'<span class="badge badge-primary gap-1">{esc(e["titulo"])}</span>'
            f'<span class="text-xs opacity-70">({occ:%H:%M})</span>'
            f'</div>'
            for occ, e in itens_hoje)
        
        label = "hoje" if d == hoje else f"{d:%d/%m/%Y}"
        return f'''<div id="proximos-eventos" class="alert alert-warning shadow-sm my-4">
                    <div class="flex items-center justify-between mb-2">
                      <span class="font-semibold" style="margin-top:.2rem">Próximos eventos de {label} ({len(itens_hoje)}):</span>
                    </div>
                    <div class="space-y-1 max-h-60 overflow-y-auto">
                      {linhas}
                    </div>
                    <button type="button" class="btn btn-xs btn-ghost btn-circle close-btn close-alert" data-close-target="proximos-eventos" title="Fechar">✕</button>
                  </div>'''
    
    # Se não há eventos para hoje, mostra mensagem e eventos de amanhã (se houver)
    # Só faz isso se o dia selecionado for hoje
    html_hoje = ('<div class="alert alert-warning shadow-sm my-4">'
                 '<div class="flex items-center justify-between mb-2">'
                 '<span class="font-semibold">Próximos eventos de hoje:</span>'
                 '</div>'
                 '<div class="flex items-center gap-2">'
                 '<span class="opacity-50">Nenhum evento futuro para hoje.</span>'
                 '</div>')
    
    html_amanha = ''
    if d == hoje:
        amanha = d + timedelta(days=1)
        itens_amanha = agenda.proximos_eventos_dia(amanha)
        if itens_amanha:
            linhas_amanha = "".join(
                f'<div class="flex items-center gap-2 p-1">'
                f'<span class="badge badge-info gap-1">{esc(e["titulo"])}</span>'
                f'<span class="text-xs opacity-70">({occ:%H:%M})</span>'
                f'</div>'
                for occ, e in itens_amanha)
            
            html_amanha = f'''
                 <div class="divider my-2">Amanhã ({amanha:%d/%m/%Y})</div>
                 <div class="space-y-1 max-h-60 overflow-y-auto">
                   {linhas_amanha}
                 </div>'''
    
    html_fechar = '<button type="button" class="btn btn-xs btn-ghost btn-circle close-btn close-alert" data-close-target="proximos-eventos" title="Fechar">✕</button>'
    html_fim = '</div>'
    
    return html_hoje + html_amanha + html_fechar + html_fim


def render_alerts_banner():
    """Renderiza banner de alerta para eventos nos próximos 30 min com fundo VERMELHO (error)."""
    itens = agenda.alertas_janela(30)
    if not itens:
        return '<div id="alerts-banner"></div>'
    agora = datetime.now()
    linhas = "".join(
        f'<span class="badge badge-error gap-1">⏰ {esc(e["titulo"])} '
        f'<span class="countdown font-mono text-lg js-alert-countdown" '
        f'data-occ-iso="{occ.strftime("%Y-%m-%dT%H:%M:%S")}">'
        f'<span class="js-cd-h" style="--value:0;" aria-live="polite" aria-label="0">00</span>'
        f':'
        f'<span class="js-cd-m" style="--value:0; --digits: 2;" aria-live="polite" aria-label="0">00</span>'
        f':'
        f'<span class="js-cd-s" style="--value:0; --digits: 2;" aria-live="polite" aria-label="0">00</span>'
        f'</span>'
        for occ, e in itens)
    return (f'<div id="alerts-banner" class="alert alert-error shadow-sm">'
            f'<div class="flex flex-wrap gap-2 items-center">'
            f'<span class="font-semibold">⚠ Eventos iniciando em 30 min:</span>{linhas}</div>'
            f'<button type="button" class="btn btn-xs btn-ghost btn-circle close-btn close-alert" data-close-target="alerts-banner" title="Fechar">✕</button>'
            f'</div>'
            f'</div>')


def format_event_datetime_br(value):
    if not value:
        return ""
    texto = str(value).strip()
    if " " in texto and "T" not in texto:
        texto = texto.replace(" ", "T")
    if texto.endswith("Z"):
        texto = texto[:-1] + "+00:00"
    try:
        if "T" in texto:
            dt = datetime.fromisoformat(texto)
            return dt.strftime("%d/%m/%Y às %H:%M")
        dt = date.fromisoformat(texto)
        return dt.strftime("%d/%m/%Y")
    except Exception:
        try:
            dt = datetime.strptime(texto, "%Y-%m-%d %H:%M")
            return dt.strftime("%d/%m/%Y às %H:%M")
        except Exception:
            return esc(value)


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
    alert_class = "alert alert-info shadow-sm mt-4" if mode == "importados" else "alert alert-success shadow-sm mt-4"
    titulo_header = "Eventos Importados do Google" if mode == "importados" else "Eventos Exportados para o Google"

    for ge in google_events:
        # ge pode ser um evento do Google (dict com 'start', 'summary') ou um dict simplificado nosso
        if 'start' in ge and 'summary' in ge:
            # Evento real do Google Calendar
            start = ge['start'].get('dateTime', ge['start'].get('date'))
            titulo = ge.get('summary', 'Sem título')
            descricao = ge.get('description', '')
            repeticao = ge.get('recurrence', '')
            until = ''
            if isinstance(repeticao, list) and repeticao:
                repeticao = repeticao[0]
        else:
            # Nosso dict simplificado (exportados/importados)
            start = ge.get('inicio', '')
            titulo = ge.get('titulo', 'Sem título')
            descricao = ge.get('desc', '') or ''
            repeticao = ge.get('repeat', '')
            until = ge.get('until', '')

        start_fmt = format_event_datetime_br(start)
        meta = []
        if repeticao:
            meta.append(esc(repeticao))
        if until:
            meta.append(f"até {esc(format_event_datetime_br(until))}")

        try:
            if 'T' in start:
                occ = datetime.fromisoformat(start.replace('Z', '+00:00'))
            else:
                occ = datetime.fromisoformat(start + 'T00:00:00')
        except Exception:
            occ = agora

        if occ.tzinfo is None:
            referencia = agora
        else:
            referencia = datetime.now(occ.tzinfo)

        faltam = int((occ - referencia).total_seconds() // 60)
        if faltam < 0:
            falta_str = f"iniciou há {abs(faltam)} min"
        else:
            falta_str = f"em {faltam} min"

        meta_html = ''.join(f'<span class="badge badge-outline badge-sm">{m}</span>' for m in meta)
        descricao_html = f'<div class="text-sm opacity-70">{linkify_urls(descricao)}</div>' if descricao else ''

        linhas.append(
            f'<div class="rounded-xl border border-base-300 bg-base-200 p-3 space-y-2">'
            f'<div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">'
            f'<span class="font-semibold">{esc(titulo)}</span>'
            f'<span class="text-xs opacity-70">{falta_str}</span>'
            f'</div>'
            f'<div class="text-sm opacity-80">{esc(start_fmt)}</div>'
            f'{descricao_html}'
            f'{f"<div class=\"flex flex-wrap gap-2 text-xs opacity-60\">{meta_html}</div>" if meta_html else ""}'
            f'</div>'
        )
    
    return f'''<div id="google-events-list-{mode}" class="{alert_class}">
                <div class="flex items-center justify-between mb-3">
                  <span class="font-semibold">{titulo_header}</span>
                  <button type="button" class="btn btn-xs btn-ghost btn-circle close-btn" data-close-target="google-events-list-{mode}" title="Fechar">✕</button>
                </div>
                <div class="space-y-3 max-h-80 overflow-y-auto">
                {"".join(linhas)}
                </div>
              </div>'''


def render_sync_status(status_msg="", detail_msg="", is_loading=False, auto_hide=False, google_events_importados=None, google_events_exportados=None, sync_logs=None):
    """Renderiza o status da sincronização e os dois quadros de eventos."""
    if is_loading:
        return f'''<div id="sync-status" class="alert alert-info shadow-sm mt-4">
                    <div class="flex flex-wrap gap-3 p-4">
                      <div class="flex items-center gap-3">
                        <span class="loading loading-spinner loading-sm"></span>
                        <span class="font-semibold">Sincronizando com Google Calendar...</span>
                      </div>
                      <div id="sync-status-detail" class="text-sm opacity-70">{esc(detail_msg)}</div>
                      <button type="button" class="btn btn-xs btn-ghost btn-circle close-btn" data-close-target="sync-status" title="Fechar">✕</button>
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
        
        # Link para abrir o modal de detalhes
        details_link = ""
        if sync_logs:
            details_link = f'''<a href="#" class="link link-hover text-xs ml-2" onclick="openSyncDetailsModal(); return false;">Exibir</a>'''
        
        html_output.append(f'''<div id="sync-status" class="alert {alert_class} shadow-sm mt-4">
          <div class="flex flex-col gap-3 p-4">
            <div class="flex items-center justify-between">
              <span class="text-lg font-semibold">Status da sincronização</span>
              <button type="button" class="btn btn-xs btn-ghost btn-circle close-btn" data-close-target="sync-status" title="Fechar">✕</button>
            </div>
            <span id="sync-status-detail" class="text-sm opacity-70">{esc(status_msg)} {esc(detail_msg)}{details_link}</span>
          </div>
        </div>{auto_hide_script}''')

        # Injetar logs no cliente para que o modal possa exibir detalhes (quando renderizado server-side)
        if sync_logs:
            try:
                logs_json = json.dumps(sync_logs, ensure_ascii=False)
            except Exception:
                logs_json = '[]'
            html_output.append(f"<script>window.syncLogsData = {logs_json};</script>")
    else:
        html_output.append('<div id="sync-status" style="display:none;"></div>')

    # Render imported events if provided
    if google_events_importados:
        html_output.append(render_google_events_list(google_events_importados, mode="importados"))
    # Render exported events if provided
    if google_events_exportados:
        html_output.append(render_google_events_list(google_events_exportados, mode="exportados"))

    return "".join(html_output)


# Modal de detalhes da sincronização (DaisyUI)
SYNC_DETAILS_MODAL = '''
  <dialog id="sync-details-modal" class="modal modal-bottom sm:modal-middle">
    <div class="modal-box max-w-2xl" style="background-color:#0b0b0b; color:#ffffff;">
      <h3 class="font-bold text-lg mb-4">Detalhes da Sincronização</h3>
      <div id="sync-details-content" class="max-h-96 overflow-y-auto space-y-2 text-sm" style="color:#ffffff;">
        <!-- Conteúdo preenchido via JS -->
      </div>
      <div class="modal-action mt-4">
        <form method="dialog">
          <button class="btn btn-primary">Fechar</button>
        </form>
      </div>
    </div>
    <form method="dialog" class="modal-backdrop">
      <button>Fechar</button>
    </form>
  </dialog>
'''

# JavaScript para o modal de detalhes da sincronização
SYNC_MODAL_JS = """
  <script>
    // Dados globais dos logs de sincronização (preenchidos pelo servidor)
    window.syncLogsData = [];

    function openSyncDetailsModal() {
      const modal = document.getElementById('sync-details-modal');
      const content = document.getElementById('sync-details-content');
      
      if (!modal || !content) return;
      
      // Renderiza os logs
      if (window.syncLogsData && window.syncLogsData.length > 0) {
        let html = '';
        let currentSection = '';
        
        window.syncLogsData.forEach(log => {
          // Detecta seções
          if (log.includes('EXPORTAÇÃO') || log.includes('Enviando eventos locais')) {
            currentSection = 'export';
            html += '<div class="font-semibold text-primary mb-1">>> EXPORTAÇÃO (Local → Google)</div>';
          } else if (log.includes('IMPORTAÇÃO') || log.includes('Buscando eventos do Google')) {
            currentSection = 'import';
            html += '<div class="font-semibold text-info mb-1">>> IMPORTAÇÃO (Google → Local)</div>';
          } else if (log.includes('Exportação para Google concluída') || 
                     log.includes('eventos importados do Google') || 
                     log.includes('Nenhum evento novo para importar')) {
            html += `<div class="text-success text-xs ml-2">${escapeHtml(log)}</div>`;
          } else if (log.includes('SIMULAÇÃO') || log.includes('Erro') || log.includes('erro')) {
            html += `<div class="text-error text-xs ml-2 font-medium">${escapeHtml(log)}</div>`;
          } else if (log.trim()) {
            html += `<div class="text-xs opacity-70 ml-2">${escapeHtml(log)}</div>`;
          }
        });
        
        content.innerHTML = html;
      } else {
        content.innerHTML = '<div class="text-center opacity-50 py-4">Nenhum detalhe disponível.</div>';
      }
      
      modal.showModal();
    }

    function escapeHtml(text) {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }

    // Fecha modal com ESC
    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') {
        const modal = document.getElementById('sync-details-modal');
        if (modal && modal.open) {
          modal.close();
        }
      }
    });
  </script>
"""

# JavaScript para o modal de confirmação de duração
DURACAO_MODAL_JS = """
  <script>
    // Modal de confirmação para duração vazia
    document.addEventListener('DOMContentLoaded', function() {
      const forms = document.querySelectorAll('form[data-duration-confirm]');
      
      forms.forEach(form => {
        form.addEventListener('submit', function(e) {
          const durInput = form.querySelector('input[name="dur"]');
          if (durInput && !durInput.value.trim()) {
            e.preventDefault();
            const modal = document.getElementById('duracao-modal');
            if (modal) {
              // Armazena o formulário para submissão posterior
              modal.dataset.pendingForm = form.id || 'unknown';
              // Adiciona ID único se não tiver
              if (!form.id) {
                form.id = 'form-' + Date.now();
                modal.dataset.pendingForm = form.id;
              }
              modal.showModal();
            }
          }
        });
      });
      
      // Botão "Sim" - submete o formulário sem duração
      const btnSim = document.getElementById('btn-duracao-sim');
      if (btnSim) {
        btnSim.addEventListener('click', function() {
          const modal = document.getElementById('duracao-modal');
          if (modal && modal.dataset.pendingForm) {
            const form = document.getElementById(modal.dataset.pendingForm);
            if (form) {
              // Remove a validação de duração e submete
              form.removeAttribute('data-duration-confirm');
              form.submit();
            }
          }
          modal.close();
        });
      }
      
      // Botão "Não" - apenas fecha o modal
      const btnNao = document.getElementById('btn-duracao-nao');
      if (btnNao) {
        btnNao.addEventListener('click', function() {
          const modal = document.getElementById('duracao-modal');
          if (modal) {
            modal.close();
          }
        });
      }
    });
  </script>
"""


def load_config_template():
    """Carrega o template de configuração do arquivo."""
    template_path = TEMPLATES_DIR / "config.htm"
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    return "<div class='alert alert-error'>Template config.htm não encontrado</div>"


def render_page(sel):
    calendar_html = render_calendar(sel.year, sel.month, sel)
    controls_html = render_controls(sel.year)
    day_panel_html = render_day_panel(sel)
    alerts_html = render_alerts_banner()
    proximos_html = render_proximos_eventos_dia(sel)
    sync_html = render_sync_status()
    config_modal_html = load_config_template()
    
    return f'''<!DOCTYPE html>
<html lang="pt-br" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Agenda Simples</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://cdn.jsdelivr.net/npm/daisyui@4/dist/full.min.css" rel="stylesheet">
  <style>
    .balloon-dark {{
      background-color: rgba(17, 24, 39, 0.96);
      color: #f8fafc;
      border: 1px solid rgba(148, 163, 184, 0.24);
      box-shadow: 0 12px 32px rgba(15, 23, 42, 0.28);
      border-radius: 0.5rem;
      padding: 0.5rem 0.75rem;
      font-size: 0.92rem;
      line-height: 1.3;
      max-width: 240px;
      word-break: break-word.
    }}
  </style>
  <script src="https://unpkg.com/htmx.org@1.9.12"></script>
  <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
  <script src="https://cdn.jsdelivr.net/gh/urin/jquery.balloon.js/jquery.balloon.min.js"></script>
  <script>
    (function () {{
      var t = localStorage.getItem("tema");
      if (t) document.documentElement.setAttribute("data-theme", t);
    }})();
  </script>
  <script src="/js/jquery-script.js"></script>
</head>
<body class="bg-base-200 min-h-screen">
  <div class="max-w-5xl mx-auto p-4 space-y-4">
    <header class="flex items-center justify-center gap-4">
      <h1 class="text-2xl font-bold">📅 Agenda Brasileira Definitiva</h1>
    </header>
    <div id="alerts-container">
        {alerts_html}
        {proximos_html}
    </div>
    <div id="sync-container">
        {sync_html}
    </div>
    <div class="grid md:grid-cols-2 gap-4">
      <div class="space-y-4">
        {calendar_html}
        {controls_html}
      </div>
      {day_panel_html}
    </div>
    <!-- esse fechamento mantem a div principal centralizada -->
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

  <!-- Modal de detalhes da sincronização -->
  {SYNC_DETAILS_MODAL}

  <!-- Modal de Configurações -->
  <dialog id="config-modal" class="modal modal-bottom sm:modal-middle">
    <div class="modal-box max-w-lg max-h-[90vh] overflow-y-auto">
      {config_modal_html}
    </div>
    <form method="dialog" class="modal-backdrop">
      <button>Fechar</button>
    </form>
  </dialog>

  {DURACAO_MODAL_JS}
  {SYNC_MODAL_JS}
</body>
</html>'''


# ------------------------------------------------------------------------- server
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            # Conexões SSE podem ser encerradas pelo navegador durante reload.
            pass

    def _send(self, corpo, status=200):
        dados = corpo.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def _send_json(self, data, status=200):
        dados = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def _write_sse(self, data):
        chunk = f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        self.wfile.write(chunk.encode("utf-8"))
        try:
            self.wfile.flush()
        except Exception:
            pass

    def _parse_date(self, texto, padrao=None):
        try:
            return datetime.strptime(texto, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return padrao or date.today()

    def _serve_static_js(self, relative_path):
        root = Path(__file__).parent
        file_path = (root / relative_path).resolve()
        if not file_path.is_file() or root not in file_path.parents and file_path != root:
            self._send("<h1>404</h1>", 404)
            return
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/javascript; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)

        if u.path.startswith("/js/"):
            self._serve_static_js(u.path.lstrip("/"))
            return

        match u.path:
            case "/":
                self._send(render_page(date.today()))
            case "/__dev_status":
                self._send_json({
                    "ok": True,
                    "pid": os.getpid(),
                    "restart_em_andamento": restart_em_andamento,
                    "sse_clients": len(sse_clients),
                    "timestamp": time_module.time(),
                })
            case "/__dev_stop":
                self._send_json({"ok": True, "msg": "Encerrando servidor..."})
                if server_instance is not None:
                    threading.Thread(target=server_instance.shutdown, daemon=True).start()
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
                d = date.today()
                alerts_banner = render_alerts_banner()
                proximos_eventos = render_proximos_eventos_dia(d)
                self._send(alerts_banner + proximos_eventos)
            case "/config":
                self._send(load_config_template())
            case "/ideas-plans":
                self._send(render_ideas_plans())
            case "/sync-stream":
                self._stream_sync_status()
            case "/export":
                self._exportar_eventos()
            case "/live-refresh":
                self._stream_live_refresh()
            case "/api/eventos-proximos":
                self._api_eventos_proximos()
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
        elif u.path == "/import":
            self._importar_eventos(corpo)
        elif u.path == "/sync-test":
            self._testar_conexao_google()
        elif u.path == "/google-reauth":
            self._reautenticar_google()
        else:
            self._send("<h1>404</h1>", 404)

    def _stream_sync_status(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        logs = []
        def on_progress(msg):
            logs.append(msg)
            self._write_sse({
                "status": msg,
                "completed": False,
                "logs": logs  # Envia logs acumulados a cada update
            })

        try:
            msg, exportados, importados, sync_logs = agenda.sync_all_with_progress(on_progress=on_progress)
            self._write_sse({
                "status": msg,
                "completed": True,
                "exportados": exportados,
                "importados": importados,
                "logs": sync_logs
            })
        except Exception as ex:
            self._write_sse({
                "status": f"Erro ao sincronizar: {ex}",
                "completed": True,
                "logs": logs
            })

    def _stream_live_refresh(self):
        """Endpoint SSE para notificações de live-refresh."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        # Registra o cliente
        client_id = id(self)
        with sse_lock:
            sse_clients.append({
                'id': client_id,
                'write': self._write_sse
            })

        try:
            # Mantém a conexão viva
            while True:
                time_module.sleep(1)
                # Envia um ping para manter a conexão ativa
                with sse_lock:
                    self._write_sse({"type": "ping"})
        except Exception:
            pass
        finally:
            # Remove o cliente quando desconecta
            with sse_lock:
                sse_clients[:] = [c for c in sse_clients if c['id'] != client_id]
            self.close_connection = True

    def _api_eventos_proximos(self):
        """API para retornar eventos próximos para notificações push."""
        agora = datetime.now()

        alertas_minutos = [60, 30, 15]
        try:
            bruto = json.loads(self.headers.get('X-Alertas-Minutos', '[60,30,15]'))
            if isinstance(bruto, list):
                filtrados = [int(v) for v in bruto if int(v) > 0]
                if filtrados:
                    alertas_minutos = sorted(set(filtrados), reverse=True)
        except Exception:
            pass

        max_min = max(alertas_minutos)
        eventos_proximos = agenda.expandir(agenda.carregar(), agora, agora + timedelta(minutes=max_min))

        eventos_list = []
        alertas_set = set(alertas_minutos)
        for occ, e in eventos_proximos:
            faltam = int((occ - agora).total_seconds() // 60)

            # Dispara apenas nos marcos exatos configurados (ex: 60, 30, 15).
            if faltam in alertas_set:
                eventos_list.append({
                    "titulo": e["titulo"],
                    "minutos_restantes": faltam,
                    "hora": occ.strftime("%H:%M"),
                    "id": e["id"]
                })
        self._send_json({"eventos": eventos_list})

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
            "concluido": False,
            "cancelado": False
        })
        agenda.salvar(eventos)
        painel = self._parse_date(form.get("panel_date")) or d
        self._responder_com_calendario(painel)
        # Notifica clientes sobre a mudança
        self._notificar_clientes()

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
            
            # Atualiza status (concluido/cancelado)
            status = form.get("status", "").strip()
            if status == "concluido":
                e["concluido"] = True
                e["cancelado"] = False
            elif status == "cancelado":
                e["cancelado"] = True
                e["concluido"] = False
            elif status == "":
                e["concluido"] = False
                e["cancelado"] = False
            
            agenda.salvar(eventos)
        self._responder_com_calendario(self._parse_date(form.get("panel_date")))
        # Notifica clientes sobre a mudança
        self._notificar_clientes()

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
        # Notifica clientes sobre a mudança
        self._notificar_clientes()

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
        # Notifica clientes sobre a mudança
        self._notificar_clientes()

    def _sincronizar_google(self):
        
        if not agenda.GOOGLE_AVAILABLE:
            self._send(render_sync_status("Bibliotecas do Google Calendar não instaladas."))
            return
        
        if not agenda.GOOGLE_CREDENTIALS_FILE.exists():
            self._send(render_sync_status("Arquivo credentials.json não encontrado."))
            return
        
        # Executa a sincronização bidirecional e obtém os resultados detalhados
        msg, exportados, importados, logs = agenda.sync_all_and_get_results()
        
        # Envia resposta com os dois painéis
        self._send(render_sync_status(msg, is_loading=False, auto_hide=True, 
                                     google_events_importados=importados,
                                     google_events_exportados=exportados,
                                     sync_logs=logs))

    def _testar_conexao_google(self):
        """Testa a conexão com Google Calendar."""
        try:
            if not agenda.GOOGLE_AVAILABLE:
                self._send_json({"ok": False, "msg": "Bibliotecas não instaladas"})
                return
            if not agenda.GOOGLE_CREDENTIALS_FILE.exists():
                self._send_json({"ok": False, "msg": "credentials.json não encontrado"})
                return
            
            service = agenda.get_google_service()
            # Tenta listar calendários para testar
            service.calendarList().list().execute()
            self._send_json({"ok": True, "msg": "Conexão OK"})
        except Exception as ex:
            self._send_json({"ok": False, "msg": str(ex)})

    def _reautenticar_google(self):
        """Remove token e força reautenticação."""
        try:
            if agenda.GOOGLE_TOKEN_FILE.exists():
                agenda.GOOGLE_TOKEN_FILE.unlink()
            # Tenta obter novo serviço (vai abrir navegador)
            service = agenda.get_google_service()
            self._send_json({"ok": True, "msg": "Reautenticação iniciada"})
        except Exception as ex:
            self._send_json({"ok": False, "msg": str(ex)})

    def _exportar_eventos(self):
        """Exporta eventos para JSON."""
        eventos = agenda.carregar()
        payload = json.dumps(eventos, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="eventos-backup-{date.today().isoformat()}.json"')
        self.send_header("Content-Length", str(len(payload)))
        # Indica que vamos fechar a conexão após enviar (ajuda clientes a finalizar download)
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)

    def _importar_eventos(self, corpo):
        """Importa eventos de JSON."""
        try:
            dados = json.loads(corpo)
            if not isinstance(dados, list):
                self._send_json({"ok": False, "msg": "Formato inválido: esperado array"})
                return
            
            eventos_atuais = agenda.carregar()
            max_id = max((e["id"] for e in eventos_atuais), default=0)
            
            count = 0
            for ev in dados:
                if "id" not in ev:
                    continue
                # Evita duplicatas por ID
                if any(e["id"] == ev["id"] for e in eventos_atuais):
                    continue
                # Ajusta ID se necessário
                if ev["id"] > max_id:
                    max_id = ev["id"]
                eventos_atuais.append(ev)
                count += 1
            
            agenda.salvar(eventos_atuais)
            self._send_json({"ok": True, "count": count})
        except Exception as ex:
            self._send_json({"ok": False, "msg": str(ex)})

    def _responder_com_calendario(self, painel):
        cal_html = render_calendar(painel.year, painel.month, painel)
        cal_oob = cal_html.replace('id="calendar"',
                                   'id="calendar" hx-swap-oob="true"', 1)
        self._send(render_day_panel(painel) + cal_oob)

    def _notificar_clientes(self):
        """Notifica todos os clientes SSE conectados sobre mudanças."""
        with sse_lock:
            for client in sse_clients[:]:
                try:
                    client['write']({"type": "refresh", "timestamp": time_module.time()})
                except Exception:
                    # Remove cliente com erro
                    sse_clients.remove(client)

    def log_message(self, *a):
        pass


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def monitorar_arquivos():
    """Monitora arquivos por mudanças e notifica clientes SSE."""
    global restart_em_andamento
    arquivos_monitorados = [
        Path(__file__).parent / "eventos.json",
        Path(__file__).parent / "agenda.py",
        Path(__file__).parent / "server.py",
        TEMPLATES_DIR / "config.htm"
    ]
    
    # Inicializa timestamps
    for arquivo in arquivos_monitorados:
        if arquivo.exists():
            file_timestamps[arquivo] = arquivo.stat().st_mtime
    
    while True:
        time_module.sleep(1)
        mudanca_detectada = False
        precisa_reiniciar = False
        
        for arquivo in arquivos_monitorados:
            if arquivo.exists():
                timestamp_atual = arquivo.stat().st_mtime
                if file_timestamps.get(arquivo) != timestamp_atual:
                    file_timestamps[arquivo] = timestamp_atual
                    mudanca_detectada = True
                if arquivo.suffix.lower() == ".py":
                  precisa_reiniciar = True
        
        if mudanca_detectada:
            # Notifica todos os clientes
            with sse_lock:
                for client in sse_clients[:]:
                    try:
                        client['write']({"type": "refresh", "timestamp": time_module.time()})
                    except Exception:
                        sse_clients.remove(client)

            # Mudanças em .py exigem reinício do processo para aplicar novo código.
            if precisa_reiniciar and not restart_em_andamento:
                restart_em_andamento = True
                print("[live-refresh] Mudança em arquivo Python detectada. Reiniciando servidor...")
                if server_instance is not None:
                    # Shutdown deve ocorrer fora da thread do servidor.
                    threading.Thread(target=server_instance.shutdown, daemon=True).start()


def ler_pid_do_arquivo():
    """Lê o PID do arquivo .agenda_server.pid."""
    try:
        if PID_FILE.exists():
            return int(PID_FILE.read_text().strip())
    except (ValueError, IOError):
        pass
    return None


def encerrar_processo_por_pid(pid):
    """Encerra o processo com o PID especificado."""
    try:
        if os.name == "nt":
            # No Windows, usa taskkill
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        else:
            # No Unix/Linux, usa kill
            os.kill(pid, signal.SIGTERM)
            return True
    except Exception:
        return False


def salvar_pid_em_arquivo():
    """Salva o PID atual no arquivo .agenda_server.pid."""
    try:
        PID_FILE.write_text(str(os.getpid()))
    except Exception:
        pass


def remover_pid_arquivo_se_for_deste_processo():
    """Remove o arquivo PID se ele pertencer a este processo."""
    try:
        if PID_FILE.exists():
            pid_arquivo = int(PID_FILE.read_text().strip())
            if pid_arquivo == os.getpid():
                PID_FILE.unlink()
    except (ValueError, IOError):
        pass


def main():
    global server_instance
    p = argparse.ArgumentParser(description="Servidor web da agenda simples.")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--host", default="127.0.0.1",
                   help="Endereço de escuta. Use 0.0.0.0 para aceitar conexões externas.")
    p.add_argument("--stop", action="store_true",
            help="Encerra o servidor em execução usando o arquivo PID e sai.")
    args = p.parse_args()

    if args.stop:
      pid = ler_pid_do_arquivo()
      if not pid:
        print("Nenhum PID encontrado para encerrar.")
        return
      ok = encerrar_processo_por_pid(pid)
      if ok:
        print(f"Servidor encerrado (PID {pid}).")
        try:
          PID_FILE.unlink(missing_ok=True)
        except Exception:
          pass
      else:
        print(f"Não foi possível encerrar o PID {pid}.")
      return
    
    # Inicia thread de monitoramento de arquivos
    monitor_thread = threading.Thread(target=monitorar_arquivos, daemon=True)
    monitor_thread.start()
    
    try:
        srv = ReusableThreadingHTTPServer((args.host, args.port), Handler)
        server_instance = srv
        salvar_pid_em_arquivo()
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
    finally:
        try:
            srv.server_close()
        except Exception:
            pass
    if not restart_em_andamento:
      remover_pid_arquivo_se_for_deste_processo()

    if restart_em_andamento:
      creation_flags = 0
      if os.name == "nt":
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
      subprocess.Popen(
        [sys.executable] + sys.argv,
        cwd=str(Path(__file__).parent),
        creationflags=creation_flags,
      )
      return


if __name__ == "__main__":
    main()

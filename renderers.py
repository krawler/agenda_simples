#!/usr/bin/env python3
"""Funções responsáveis por renderizar as páginas HTML do app."""

import calendar as calmod
import html
import json
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
import agenda

WEEKDAYS = ["Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"]
TEMAS = ["light", "dark", "cupcake", "corporate", "emerald", "synthwave",
         "dracula", "night", "coffee", "winter"]
MESES = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
         "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
ANOS_DISPONIVEIS = [2025, 2026, 2027, 2028]
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
RENDERERS_DIR = TEMPLATES_DIR / "renderers"
env = Environment(
  loader=FileSystemLoader(str(RENDERERS_DIR)),
  autoescape=select_autoescape(["html", "htm", "xml"]),
)


def _render_template(name, **context):
  try:
    template = env.get_template(name)
  except Exception:
    return f"<div class='alert alert-error'>Template {name} não encontrado</div>"
  return template.render(**context)


def esc(v):
    return html.escape(str(v)) if v is not None else ""


def linkify_urls(text):
    """Converte URLs em texto para links clicáveis."""
    if not text:
        return ""
    url_pattern = re.compile(
        r'(?i)\b((?:https?://|ftp://|file://|mailto:|www\.)[^\s<>"\']+)'
    )

    def replace_url(match):
        url = match.group(1)
        href = url if re.match(r'^[a-z]+://', url, re.I) else 'http://' + url
        return f'<a href="{esc(href)}" target="_blank" rel="noopener noreferrer" class="link link-primary underline">{esc(url)}</a>'

    return url_pattern.sub(replace_url, text)


def load_config_template():
    """Carrega o template de configuração do arquivo."""
    template_path = TEMPLATES_DIR / "config.htm"
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    return "<div class='alert alert-error'>Template config.htm não encontrado</div>"


def render_calendar(ano, mes, sel):
    hoje = date.today()
    prev_ano, prev_mes = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
    next_ano, next_mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
    com_eventos = dias_com_eventos(ano, mes)
    contagem_eventos = contagem_eventos_por_dia(ano, mes)

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
            contagem = contagem_eventos.get(d, 0)
            count_html = ''
            if contagem > 0:
                count_html = (
                    f'<span class="leading-none mt-0.5" '
                    f'style="font-size: 10px; line-height: 1; opacity: 0.7;">'
                    f'{contagem}</span>'
                )
            ponto = ('<span class="w-1.5 h-1.5 rounded-full bg-accent absolute '
                     'bottom-1"></span>') if d in com_eventos else ""
            celulas.append(
                f'<button class="{" ".join(classes)}" '
                f'hx-get="/day?date={iso}" hx-target="#day-panel">'
                f'<div class="flex items-center justify-center gap-1">'
                f'<span>{dia}</span>{count_html}</div>{ponto}</button>')

    return _render_template(
        "calendar.html",
        ano=ano,
        mes=mes,
        sel=sel,
        prev_ano=prev_ano,
        prev_mes=prev_mes,
        next_ano=next_ano,
        next_mes=next_mes,
        meses=MESES,
        cabecalho=cabecalho,
        celulas="".join(celulas),
    )


def eventos_do_dia(d):
    wstart = datetime.combine(d, time.min)
    wend = datetime.combine(d, time.max)
    return agenda.expandir(agenda.carregar(), wstart, wend)


def dias_com_eventos(ano, mes):
    ultimo = calmod.monthrange(ano, mes)[1]
    wstart = datetime.combine(date(ano, mes, 1), time.min)
    wend = datetime.combine(date(ano, mes, ultimo), time.max)
    return {occ.date() for occ, _ in agenda.expandir(agenda.carregar(), wstart, wend)}


def contagem_eventos_por_dia(ano, mes):
    ultimo = calmod.monthrange(ano, mes)[1]
    wstart = datetime.combine(date(ano, mes, 1), time.min)
    wend = datetime.combine(date(ano, mes, ultimo), time.max)
    contagem = {}
    for occ, _ in agenda.expandir(agenda.carregar(), wstart, wend):
        dia = occ.date()
        contagem[dia] = contagem.get(dia, 0) + 1
    return contagem


def render_controls(ano_atual=None):
    """Renderiza os controles (botões, seletor de ano) para ficar abaixo do calendário."""
    return _render_template("controls.html", ano_atual=ano_atual)


def render_evento_item(occ, e):
    dur = ""
    if e.get("dur"):
        fim = occ + timedelta(minutes=e["dur"])
        dur = f"–{fim:%H:%M}"
    badges = ""
    if e.get("repeat"):
        badges += (f'<span class="badge badge-sm badge-outline">'
                   f'{esc(e["repeat"])}</span>')
    iso = occ.date().isoformat()
    editar = (f'hx-get="/edit?id={e["id"]}&date={iso}" '
              f'hx-target="#day-panel"')

    status_indicador = ""
    agora = datetime.now()
    progresso = 0
    if e.get("dur") and occ:
        duracao_segundos = e["dur"] * 60
        passado_segundos = (agora - occ).total_seconds()
        progresso = max(0, min(100, int((passado_segundos / duracao_segundos) * 100)))

    if e.get("cancelado"):
        status_indicador = '<span class="text-red-400 font-medium">(evento cancelado)</span>'
    elif e.get("concluido") and occ > agora:
        status_indicador = '<span class="text-green-700 font-medium">(evento concluído)</span>'

    desc = (f'<div {editar} class="text-sm opacity-70 hover:underline cursor-pointer">{linkify_urls(e["desc"])}</div>'
            if e.get("desc") else "")

    if e.get("repeat"):
        acoes = f'''<div class="dropdown dropdown-end">
      <button tabindex="0" class="btn btn-xs btn-ghost">⋯</button>
      <ul tabindex="0" class="dropdown-content z-10 menu p-2 shadow bg-base-100 rounded-box w-44">
        <li><a hx-post="/skip?id={e["id"]}&date={iso}" hx-target="#day-panel">
          ⤵ Pular este dia</a></li>
        <li><a class="text-error"
          hx-post="/delete?id={e["id"]}&date={iso}" hx-target="#day-panel"
          hx-confirm="Remover a série inteira '{esc(e["titulo"])}'?">🗑 Remover série</a></li>
      </ul>
    </div>'''
    else:
        acoes = f'''<div class="flex justify-end gap-1">
      <button class="btn btn-xs btn-ghost text-error"
        hx-post="/delete?id={e["id"]}&date={iso}" hx-target="#day-panel"
        hx-confirm="Remover '{esc(e["titulo"])}'?">✕</button>
    </div>'''

    return _render_template(
        "evento_item.html",
        occ=occ,
        dur=dur,
        duracao_minutos=e.get("dur"),
        progresso=progresso,
        editar=editar,
        badges=badges,
        status_indicador=status_indicador,
        desc=desc,
        acoes=acoes,
        titulo=esc(e["titulo"]),
    )


def render_edit_form(e, occ, panel_date):
    base = agenda.evento_inicio(e)
    iso = panel_date.isoformat()
    opts = "".join(
        f'<option value="{r}"{" selected" if r == (e.get("repeat") or "none") else ""}>'
        f'{"sem repetição" if r == "none" else r}</option>'
        for r in agenda.REPEATS)

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

    return _render_template(
        "edit_form.html",
        e=e,
        iso=iso,
        titulo=esc(e["titulo"]),
        base_date=base.date().isoformat(),
        base_time=f"{base:%H:%M}",
        dur=e.get("dur") or "",
        opts=opts,
        until=esc(e.get("until") or ""),
        status_opts=status_opts,
        desc=esc(e.get("desc") or ""),
    )


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

    return _render_template(
        "day_panel.html",
        d=d,
        weekdays=WEEKDAYS,
        lista=lista,
        novo_evento=novo_evento,
    )


def render_proximos_eventos_dia(d):
    """Renderiza lista dos próximos eventos do dia com fundo amarelo."""
    hoje = date.today()
    itens_hoje = agenda.proximos_eventos_dia(d)

    if itens_hoje:
        linhas = "".join(
            f'<div class="flex items-center gap-2 p-1">'
            f'<span class="badge badge-primary gap-1">{esc(e["titulo"])}</span>'
            f'<span class="text-xs opacity-70">({occ:%H:%M})</span>'
            f'</div>'
            for occ, e in itens_hoje)

        label = "hoje" if d == hoje else f"{d:%d/%m/%Y}"
        return _render_template(
            "proximos_eventos.html",
            label=label,
            count=len(itens_hoje),
            linhas=linhas,
        )

    return _render_template(
        "proximos_eventos.html",
        label="hoje",
        count=0,
        linhas='<div class="flex items-center gap-2"><span class="opacity-50">Nenhum evento futuro para hoje.</span></div>',
    )


def render_alerts_banner():
    """Renderiza banner de alerta para eventos nos próximos 30 min."""
    itens = agenda.alertas_janela(30)
    occ_date = None
    if not itens:
      return '<div id="alerts-banner"></div>'
    linhas = "".join(
        f'<span class="badge badge-error gap-1">⏰ {esc(e["titulo"])} '
        f'</span>'
        for occ, e in itens)
    if itens:
        occ_date = itens[0][0].strftime("%Y-%m-%dT%H:%M:%S")
    return _render_template("alerts_banner.html", linhas=linhas, occ_date=occ_date)


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
    """Renderiza lista de eventos do Google Calendar."""
    if not google_events and mode == "importados":
        return '<div class="alert alert-base-200 shadow-sm"><div class="flex items-center gap-2"><span class="opacity-50">Nenhum evento encontrado no Google Calendar.</span></div></div>'
    elif not google_events and mode == "exportados":
        return '<div class="alert alert-base-200 shadow-sm"><div class="flex items-center gap-2"><span class="opacity-50">Nenhum evento encontrado no calendário local.</span></div></div>'

    agora = datetime.now()
    linhas = []
    alert_class = "alert alert-info shadow-sm mt-4" if mode == "importados" else "alert alert-success shadow-sm mt-4"
    titulo_header = "Eventos Importados do Google" if mode == "importados" else "Eventos Exportados para o Google"

    for ge in google_events:
        if 'start' in ge and 'summary' in ge:
            start = ge['start'].get('dateTime', ge['start'].get('date'))
            titulo = ge.get('summary', 'Sem título')
            descricao = ge.get('description', '')
            repeticao = ge.get('recurrence', '')
            until = ''
            if isinstance(repeticao, list) and repeticao:
                repeticao = repeticao[0]
        else:
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

    return _render_template(
      "google_events_list.html",
      mode=mode,
      alert_class=alert_class,
      titulo_header=titulo_header,
      linhas="".join(linhas),
    )


def render_sync_status(status_msg="", detail_msg="", is_loading=False, auto_hide=False, google_events_importados=None, google_events_exportados=None, sync_logs=None):
    """Renderiza o status da sincronização e os dois quadros de eventos."""
    if is_loading:
      return _render_template(
        "sync_status.html",
            alert_class="alert-info",
            status_msg="Sincronizando com Google Calendar...",
            detail_msg=esc(detail_msg),
            details_link="",
            auto_hide_script=""
      )

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

        details_link = ""
        if sync_logs:
            details_link = f'''<a href="#" class="link link-hover text-xs ml-2" onclick="openSyncDetailsModal(); return false;">Exibir</a>'''

        html_output.append(_render_template(
          "sync_status.html",
            alert_class=alert_class,
            status_msg=esc(status_msg),
            detail_msg=esc(detail_msg),
            details_link=details_link,
            auto_hide_script=auto_hide_script
        ))

        if sync_logs:
            try:
                logs_json = json.dumps(sync_logs, ensure_ascii=False)
            except Exception:
                logs_json = '[]'
            html_output.append(f"<script>window.syncLogsData = {logs_json};</script>")
    else:
        html_output.append('<div id="sync-status" style="display:none;"></div>')

    if google_events_importados:
        html_output.append(render_google_events_list(google_events_importados, mode="importados"))
    if google_events_exportados:
        html_output.append(render_google_events_list(google_events_exportados, mode="exportados"))

    return "".join(html_output)


SYNC_DETAILS_MODAL = '''
  <dialog id="sync-details-modal" class="modal modal-bottom sm:modal-middle">
    <div class="modal-box max-w-2xl" style="background-color:#0b0b0b; color:#ffffff;">
      <h3 class="font-bold text-lg mb-4">Detalhes da Sincronização</h3>
      <div id="sync-details-content" class="max-h-96 overflow-y-auto space-y-2 text-sm" style="color:#ffffff;">
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

SYNC_MODAL_JS = """
  <script>
    window.syncLogsData = [];

    function openSyncDetailsModal() {
      const modal = document.getElementById('sync-details-modal');
      const content = document.getElementById('sync-details-content');

      if (!modal || !content) return;

      if (window.syncLogsData && window.syncLogsData.length > 0) {
        let html = '';
        let currentSection = '';

        window.syncLogsData.forEach(log => {
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

DURACAO_MODAL_JS = """
  <script>
    document.addEventListener('DOMContentLoaded', function() {
      const forms = document.querySelectorAll('form[data-duration-confirm]');

      forms.forEach(form => {
        form.addEventListener('submit', function(e) {
          const durInput = form.querySelector('input[name="dur"]');
          if (durInput && !durInput.value.trim()) {
            e.preventDefault();
            const modal = document.getElementById('duracao-modal');
            if (modal) {
              modal.dataset.pendingForm = form.id || 'unknown';
              if (!form.id) {
                form.id = 'form-' + Date.now();
                modal.dataset.pendingForm = form.id;
              }
              modal.showModal();
            }
          }
        });
      });

      const btnSim = document.getElementById('btn-duracao-sim');
      if (btnSim) {
        btnSim.addEventListener('click', function() {
          const modal = document.getElementById('duracao-modal');
          if (modal && modal.dataset.pendingForm) {
            const form = document.getElementById(modal.dataset.pendingForm);
            if (form) {
              form.removeAttribute('data-duration-confirm');
              form.submit();
            }
          }
          modal.close();
        });
      }

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


def render_page(sel):
  calendar_html = render_calendar(sel.year, sel.month, sel)
  controls_html = render_controls(sel.year)
  day_panel_html = render_day_panel(sel)
  alerts_html = render_alerts_banner()
  sync_html = render_sync_status()
  config_modal_html = load_config_template()
  return _render_template(
    "page.html",
    calendar_html=calendar_html,
    controls_html=controls_html,
    day_panel_html=day_panel_html,
    alerts_html=alerts_html,
    sync_html=sync_html,
    config_modal_html=config_modal_html,
    sync_details_modal=SYNC_DETAILS_MODAL,
    sync_modal_js=SYNC_MODAL_JS,
    duracao_modal_js=DURACAO_MODAL_JS,
  )

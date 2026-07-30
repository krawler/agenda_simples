#!/usr/bin/env python3
"""Servidor web da agenda simples.

Roteamento:
  /          → página principal (agenda)
  /eventos   → lista de eventos
  /sync      → sincroniza com Google Calendar
  /alertas   → lista de alertas
  /sync/…    → endpoints de sincronização
  /api/…     → endpoints de API (ex.: criar, atualizar, remover)

A página principal exibe:
  • Um cabeçalho com título, seletor de tema e botões de ação
  • Um calendário mensal com eventos
  • Um banner de alertas
  • Um painel de sincronização

O layout é responsivo: em telas pequenas o cabeçalho se adapta colocando os controles
na linha abaixo do título.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import agenda  # reutiliza carregar()/expandir()/ALERTA_MIN

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# --------------------------------------------------------------------- config
def carregar_env(caminho):
    """Carrega KEY=VALUE de um .env simples, sem sobrescrever o ambiente."""
    p = Path(caminho)
    if not p.exists():
        return
    for linha in p.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


def carregar_config():
    """Carrega e valida a config. Email e Telegram sao opcionais (nao bloqueantes)."""
    config = {}

    # E-mail (opcional)
    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    senha = os.environ.get("SMTP_PASSWORD")
    to = os.environ.get("AGENDA_EMAIL_TO")
    if all([host, user, senha, to]):
        config["email"] = {
            "host": host,
            "port": int(os.environ.get("SMTP_PORT", "587")),
            "user": user,
            "password": senha,
            "from": os.environ.get("SMTP_FROM") or user,
            "to": to,
        }

    # Telegram (opcional)
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    tg_chat = os.environ.get("TELEGRAM_CHAT_ID")
    if tg_token and tg_chat:
        config["telegram"] = {
            "token": tg_token,
            "chat_id": tg_chat,
        }

    if not config:
        sys.exit("Nenhum serviço de notificacao configurado.\n"
                 "Configure SMTP (email) e/ou Telegram via .env ou variáveis de ambiente.")
    return config


# ------------------------------------------------------------------ dedup db
def carregar_enviados():
    if ENVIADOS.exists():
        return set(json.loads(ENVIADOS.read_text(encoding="utf-8")))
    return set()


def salvar_enviados(chaves, agora):
    """Persiste as chaves, descartando ocorrencias com mais de 1 dia."""
    limite = agora - timedelta(days=1)
    manter = []
    for k in chaves:
        try:
            occ = datetime.fromisoformat(k.split("|", 2)[2])
        except (ValueError, IndexError):
            continue
        if occ >= limite:
            manter.append(k)
    ENVIADOS.write_text(json.dumps(sorted(manter), ensure_ascii=False, indent=2),
                        encoding="utf-8")


# ------------------------------------------------------------------ mensagens
def montar_mensagem(e, occ):
    """Monta o conteúdo da notificação (usado por email e Telegram)."""
    ini = occ
    fim = ini + timedelta(minutes=e["dur"]) if e.get("dur") else None
    quando = f"{ini:%d/%m/%Y %H:%M}" + (f"–{fim:%H:%M}" if fim else "")

    linhas = [f"Lembrete: seu evento começa em breve.", "",
              f"• Evento: {e['titulo']}",
              f"• Quando: {quando}"]
    if e.get("dur"):
        linhas.append(f"• Duração: {e['dur']} min")
    if e.get("desc"):
        linhas.append(f"• Descrição: {e['desc']}")
    if e.get("repeat"):
        linhas.append(f"• Recorrência: {e['repeat']}")
    linhas += ["", "— Agenda Simples"]
    return "\n".join(linhas)


# ------------------------------------------------------------------ e-mail
def montar_email(e, occ, cfg):
    msg = EmailMessage()
    msg["Subject"] = f"⏰ Lembrete: {e['titulo']} às {occ:%H:%M}"
    msg["From"] = cfg["from"]
    msg["To"] = e.get("to") or cfg["to"]
    msg.set_content(montar_mensagem(e, occ))
    return msg


def enviar_email(msg, cfg):
    import smtplib

    if cfg["port"] == 465:
        with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=30) as s:
            s.login(cfg["user"], cfg["password"])
            s.send_message(msg)
    else:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as s:
            s.starttls()
            s.login(cfg["user"], cfg["password"])
            s.send_message(msg)


# ------------------------------------------------------------------ telegram
def enviar_telegram(titulo, mensagem, cfg):
    """Envia via API do Telegram (returns True se sucesso)."""
    url = f"https://api.telegram.org/bot{cfg['token']}/sendMessage"
    dados = urlencode({"chat_id": cfg["chat_id"], "text": mensagem})
    try:
        req = Request(url, data=dados.encode("utf-8"))
        urlopen(req, timeout=30)
        return True
    except Exception as ex:
        print(f"[erro Telegram] {ex}", file=sys.stderr)
        return False


# ------------------------------------------------------------------ renderização
def render_calendar(ano, mes, sel):
    """Renderiza o calendário mensal com eventos."""
    # ... (código existente) ...


def render_evento_item(occ, e):
    """Renderiza um evento dentro de um dia."""
    # ... (código existente) ...


def render_edit_form(e, occ, panel_date):
    """Renderiza o formulário de edição de evento."""
    # ... (código existente) ...


def render_day_panel(d, editando=None):
    """Renderiza um painel de dia no calendário."""
    # ... (código existente) ...


def render_alerts_banner():
    """Renderiza o banner de alertas."""
    # ... (código existente) ...


def render_sync_status(status_msg="", is_loading=False):
    """Renderiza o painel de sincronização."""
    # ... (código existente) ...


def render_page(sel):
    """Renderiza a página principal."""
    # Cabeçalho responsivo
    header = f"""
    <header class="topbar">
        <h1 class="title">Agenda Simples</h1>
        <div class="controls">
            <label for="theme-select">Tema:</label>
            <select id="theme-select" onchange="changeTheme(this.value)">
                <option value="light" {'selected' if sel['theme']=='light' else ''}>Claro</option>
                <option value="dark" {'selected' if sel['theme']=='dark' else ''}>Escuro</option>
            </select>
            <button onclick="location.href='/sync'">Sincronizar</button>
            <button onclick="location.href='/eventos'">Eventos</button>
        </div>
    </header>
    """

    # Estilos CSS (responsivo)
    styles = """
    <style>
    body {font-family: Arial, sans-serif; margin:0; padding:0;}
    .topbar {display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; padding:10px; background:#f0f0f0;}
    .topbar .title {margin:0; font-size:1.5em;}
    .topbar .controls {display:flex; flex-wrap:wrap; gap:10px; align-items:center;}
    .topbar .controls label {margin-right:5px;}
    .topbar .controls select, .topbar .controls button {padding:5px 10px;}
    @media (max-width: 600px) {
        .topbar {flex-direction:column; align-items:flex-start;}
        .topbar .controls {margin-top:5px;}
    }
    </style>
    """

    # Corpo da página
    body = f"""
    {header}
    {styles}
    <main>
        {render_calendar(sel['ano'], sel['mes'], sel)}
        {render_alerts_banner()}
        {render_sync_status()}
    </main>
    """

    return body


# --------------------------------------------------------------------- handler
class Handler(BaseHTTPRequestHandler):
    def _send(self, corpo, status=200):
        dados = corpo.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def _parse_date(self, texto, padrao=None):
        # ... (código existente) ...
        pass

    def do_GET(self):
        # ... (código existente) ...
        pass

    def do_POST(self):
        # ... (código existente) ...
        pass

    def _criar_evento(self, form):
        # ... (código existente) ...
        pass

    def _atualizar_evento(self, form):
        # ... (código existente) ...
        pass

    def _remover_evento(self, q):
        # ... (código existente) ...
        pass

    def _pular_ocorrencia(self, q):
        # ... (código existente) ...
        pass

    def _sincronizar_google(self):
        """Endpoint para sincronizar com Google Calendar."""
        # ... (código existente) ...
        pass

    def _responder_com_calendario(self, painel):
        # ... (código existente) ...
        pass

    def log_message(self, *a):  # silencia log padrao ruidoso
        pass


def main():
    p = argparse.ArgumentParser(description="Servidor da agenda simples.")
    p.add_argument("--port", type=int, default=8000, help="porta do servidor")
    args = p.parse_args()

    servidor = HTTPServer(("0.0.0.0", args.port), Handler)
    print(f"Servidor rodando em http://localhost:{args.port}")
    servidor.serve_forever()


if __name__ == "__main__":
    main()

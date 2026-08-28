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
from renderers import (
    render_calendar,
    render_controls,
    render_day_panel,
    render_alerts_banner,
    render_proximos_eventos_dia,
    render_sync_status,
    render_page,
    load_config_template,
)
from inc.funcoes_agenda import (
    ler_pid_do_arquivo,
    encerrar_processo_por_pid,
    salvar_pid_em_arquivo,
    remover_pid_arquivo_se_for_deste_processo,
)
from inc.Handler import Handler

TEMPLATES_DIR = Path(__file__).parent / "templates"

# Armazenar conexões SSE ativas
sse_clients = []

# Armazenar timestamps de arquivos monitoradas
file_timestamps = {}

# Flag para evitar múltiplos restarts simultâneos
restart_state = {"value": False}

# Instância global do servidor para permitir shutdown coordenado.
server_instance_state = {"value": None}

# Arquivo PID para controle do servidor em modo dev.
PID_FILE = Path(__file__).parent / ".agenda_server.pid"

# Lock para acesso thread-safe aos clientes SSE
sse_lock = threading.Lock()

class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def monitorar_arquivos():
    """Monitora arquivos por mudanças e notifica clientes SSE."""
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
            if precisa_reiniciar and not restart_state["value"]:
                restart_state["value"] = True
                print("[live-refresh] Mudança em arquivo Python detectada. Reiniciando servidor...")
                if server_instance_state["value"] is not None:
                    # Shutdown deve ocorrer fora da thread do servidor.
                    threading.Thread(target=server_instance_state["value"].shutdown, daemon=True).start()


def main():
    p = argparse.ArgumentParser(description="Servidor web da agenda simples.")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--host", default="127.0.0.1",
                   help="Endereço de escuta. Use 0.0.0.0 para aceitar conexões externas.")
    p.add_argument("--stop", action="store_true",
                   help="Encerra o servidor em execução usando o arquivo PID e sai.")
    p.add_argument("--no-live-refresh", action="store_true",
                   help="Desativa o monitor de arquivos e reinício automático (útil para depuração).")
    args = p.parse_args()

    # Habilita no-live-refresh quando variável de ambiente estiver presente
    if os.environ.get("DEV_NO_LIVEREFRESH"):
        args.no_live_refresh = True

    Handler.configure(
        agenda=agenda,
        render_calendar=render_calendar,
        render_controls=render_controls,
        render_day_panel=render_day_panel,
        render_alerts_banner=render_alerts_banner,
        render_proximos_eventos_dia=render_proximos_eventos_dia,
        render_sync_status=render_sync_status,
        render_page=render_page,
        load_config_template=load_config_template,
        sse_clients=sse_clients,
        sse_lock=sse_lock,
        restart_state=restart_state,
        server_instance=server_instance_state,
        templates_dir=TEMPLATES_DIR,
    )

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
    
    # Inicia thread de monitoramento de arquivos (salvo quando desativado)
    if not args.no_live_refresh:
        monitor_thread = threading.Thread(target=monitorar_arquivos, daemon=True)
        monitor_thread.start()
    
    try:
        srv = ReusableThreadingHTTPServer((args.host, args.port), Handler)
        server_instance_state["value"] = srv
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
    if not restart_state["value"]:
      remover_pid_arquivo_se_for_deste_processo()

    if restart_state["value"]:
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

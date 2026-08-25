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
    eventos_do_dia,
    dias_com_eventos,
    ler_pid_do_arquivo,
    encerrar_processo_por_pid,
    salvar_pid_em_arquivo,
    remover_pid_arquivo_se_for_deste_processo,
)

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
# (funções movidas para inc/funcoes_agenda.py)


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

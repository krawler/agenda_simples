#!/usr/bin/env python3
"""Handler HTTP da interface web da agenda simples."""

import json
import time as time_module
from datetime import date, datetime, time
from http.server import BaseHTTPRequestHandler
from pathlib import Path

import ideias

from inc.handler_logic import (
	build_nearby_events_payload,
	import_events,
	merge_event_update,
	parse_alerts_minutes,
	parse_event_form,
)


class Handler(BaseHTTPRequestHandler):
	protocol_version = "HTTP/1.1"

	agenda = None
	render_calendar = None
	render_controls = None
	render_day_panel = None
	render_alerts_banner = None
	render_proximos_eventos_dia = None
	render_sync_status = None
	render_page = None
	render_ideas_plans = None
	load_config_template = None
	sse_clients = None
	sse_lock = None
	restart_state = None
	server_instance = None
	templates_dir = None

	@classmethod
	def configure(cls, **kwargs):
		for key, value in kwargs.items():
			setattr(cls, key, value)

	def handle(self):
		try:
			super().handle()
		except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
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
		root = Path(__file__).resolve().parents[1]
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
		from urllib.parse import parse_qs, urlparse

		u = urlparse(self.path)
		q = parse_qs(u.query)

		if u.path.startswith("/js/"):
			self._serve_static_js(u.path.lstrip("/"))
			return

		match u.path:
			case "/":
				self._send(self.render_page(date.today()))
			case "/__dev_status":
				self._send_json({
					"ok": True,
					"pid": __import__("os").getpid(),
					"restart_em_andamento": self.restart_state["value"],
					"sse_clients": len(self.sse_clients),
					"timestamp": time_module.time(),
				})
			case "/__dev_stop":
				self._send_json({"ok": True, "msg": "Encerrando servidor..."})
				if self.server_instance["value"] is not None:
					import threading
					threading.Thread(target=self.server_instance["value"].shutdown, daemon=True).start()
			case "/day":
				d = self._parse_date(q.get("date", [""])[0])
				self._send(self.render_day_panel(d))
			case "/edit":
				d = self._parse_date(q.get("date", [""])[0])
				eid = int(q.get("id", ["0"])[0])
				self._send(self.render_day_panel(d, editando=eid))
			case "/calendar":
				try:
					ano = int(q.get("year", [date.today().year])[0])
					mes = int(q.get("month", [date.today().month])[0])
					sel = self._parse_date(q.get("sel", [""])[0])
					self._send(self.render_calendar(ano, mes, sel))
				except ValueError:
					ano = date.today().year
					mes = max(1, min(12, date.today().month))
					sel = self._parse_date(q.get("sel", [""])[0])
					self._send(self.render_calendar(ano, mes, sel))
			case "/alerts":
				d = date.today()
				alerts_banner = self.render_alerts_banner()
				proximos_eventos = self.render_proximos_eventos_dia(d)
				self._send(alerts_banner + proximos_eventos)
			case "/config":
				self._send(self.load_config_template())
			case "/ideas-plans":
				self._send(self.render_ideas_plans())
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
		from urllib.parse import parse_qs, urlparse

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
		elif u.path == "/idea":
			self._criar_ideia(form)
		elif u.path == "/idea/delete":
			self._remover_ideia(q)
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
			self._write_sse({"status": msg, "completed": False, "logs": logs})

		try:
			msg, exportados, importados, sync_logs = self.agenda.sync_all_with_progress(on_progress=on_progress)
			self._write_sse({"status": msg, "completed": True, "exportados": exportados, "importados": importados, "logs": sync_logs})
		except Exception as ex:
			self._write_sse({"status": f"Erro ao sincronizar: {ex}", "completed": True, "logs": logs})

	def _stream_live_refresh(self):
		self.send_response(200)
		self.send_header("Content-Type", "text/event-stream; charset=utf-8")
		self.send_header("Cache-Control", "no-cache")
		self.send_header("Connection", "keep-alive")
		self.end_headers()

		client_id = id(self)
		with self.sse_lock:
			self.sse_clients.append({"id": client_id, "write": self._write_sse})

		try:
			while True:
				time_module.sleep(1)
				with self.sse_lock:
					self._write_sse({"type": "ping"})
		except Exception:
			pass
		finally:
			with self.sse_lock:
				self.sse_clients[:] = [c for c in self.sse_clients if c["id"] != client_id]
			self.close_connection = True

	def _api_eventos_proximos(self):
		payload = build_nearby_events_payload(
			self.agenda.carregar,
			self.agenda.expandir,
			datetime.now(),
			parse_alerts_minutes(self.headers.get("X-Alertas-Minutos", "[60,30,15]")),
		)
		self._send_json(payload)

	def _criar_evento(self, form):
		info = parse_event_form(form, self.agenda, self._parse_date)

		eventos = self.agenda.carregar()
		eventos.append({"id": self.agenda.proximo_id(eventos), "titulo": info["titulo"], "inicio": info["inicio"].strftime(self.agenda.FMT), "dur": info["dur"], "desc": info["desc"], "repeat": info["repeat"], "until": info["until"], "concluido": False, "cancelado": False})
		self.agenda.salvar(eventos)
		painel = self._parse_date(form.get("panel_date")) or info["date"]
		self._responder_com_calendario(painel)
		self._notificar_clientes()

	def _atualizar_evento(self, form):
		eid = int(form.get("id", "0"))
		eventos = self.agenda.carregar()
		e = next((x for x in eventos if x["id"] == eid), None)
		if e is not None:
			merge_event_update(e, form, self.agenda, self._parse_date)
			self.agenda.salvar(eventos)
		self._responder_com_calendario(self._parse_date(form.get("panel_date")))
		self._notificar_clientes()

	def _remover_evento(self, q):
		eid = int(q.get("id", ["0"])[0])
		eventos = self.agenda.carregar()
		evento = next((x for x in eventos if x["id"] == eid), None)
		if evento and self.agenda.GOOGLE_AVAILABLE and evento.get("google_id"):
			try:
				self.agenda.delete_event_from_google(evento)
			except Exception:
				pass
		eventos = [e for e in self.agenda.carregar() if e["id"] != eid]
		self.agenda.salvar(eventos)
		painel = self._parse_date(q.get("date", [""])[0])
		self._responder_com_calendario(painel)
		self._notificar_clientes()

	def _pular_ocorrencia(self, q):
		eid = int(q.get("id", ["0"])[0])
		dia = self._parse_date(q.get("date", [""])[0]).isoformat()
		eventos = self.agenda.carregar()
		e = next((x for x in eventos if x["id"] == eid), None)
		if e is not None:
			excecoes = set(e.get("except") or [])
			excecoes.add(dia)
			e["except"] = sorted(excecoes)
			self.agenda.salvar(eventos)
		self._responder_com_calendario(self._parse_date(q.get("date", [""])[0]))
		self._notificar_clientes()

	def _sincronizar_google(self):
		if not self.agenda.GOOGLE_AVAILABLE:
			self._send(self.render_sync_status("Bibliotecas do Google Calendar não instaladas."))
			return
		if not self.agenda.GOOGLE_CREDENTIALS_FILE.exists():
			self._send(self.render_sync_status("Arquivo credentials.json não encontrado."))
			return
		msg, exportados, importados, logs = self.agenda.sync_all_and_get_results()
		self._send(self.render_sync_status(msg, is_loading=False, auto_hide=True, google_events_importados=importados, google_events_exportados=exportados, sync_logs=logs))

	def _testar_conexao_google(self):
		try:
			if not self.agenda.GOOGLE_AVAILABLE:
				self._send_json({"ok": False, "msg": "Bibliotecas não instaladas"})
				return
			if not self.agenda.GOOGLE_CREDENTIALS_FILE.exists():
				self._send_json({"ok": False, "msg": "credentials.json não encontrado"})
				return
			service = self.agenda.get_google_service()
			service.calendarList().list().execute()
			self._send_json({"ok": True, "msg": "Conexão OK"})
		except Exception as ex:
			self._send_json({"ok": False, "msg": str(ex)})

	def _reautenticar_google(self):
		try:
			if self.agenda.GOOGLE_TOKEN_FILE.exists():
				self.agenda.GOOGLE_TOKEN_FILE.unlink()
			self.agenda.get_google_service()
			self._send_json({"ok": True, "msg": "Reautenticação iniciada"})
		except Exception as ex:
			self._send_json({"ok": False, "msg": str(ex)})

	def _exportar_eventos(self):
		eventos = self.agenda.carregar()
		payload = json.dumps(eventos, ensure_ascii=False, indent=2).encode("utf-8")
		self.send_response(200)
		self.send_header("Content-Type", "application/json; charset=utf-8")
		self.send_header("Content-Disposition", f'attachment; filename="eventos-backup-{date.today().isoformat()}.json"')
		self.send_header("Content-Length", str(len(payload)))
		self.send_header("Connection", "close")
		self.end_headers()
		self.wfile.write(payload)

	def _importar_eventos(self, corpo):
		try:
			dados = json.loads(corpo)
			if not isinstance(dados, list):
				self._send_json({"ok": False, "msg": "Formato inválido: esperado array"})
				return
			eventos_atuais, count = import_events(self.agenda.carregar(), dados)
			self.agenda.salvar(eventos_atuais)
			self._send_json({"ok": True, "count": count})
		except Exception as ex:
			self._send_json({"ok": False, "msg": str(ex)})

	def _criar_ideia(self, form):
		nome = (form.get("nome") or "").strip()
		descricao = (form.get("descricao") or "").strip()
		try:
			ideias.criar_ideia(nome, descricao or None)
		except ValueError as exc:
			self._send(self.render_ideas_plans(error_message=str(exc)))
			return
		self._send(self.render_ideas_plans())

	def _remover_ideia(self, q):
		ideia_id = q.get("id", ["0"])[0]
		try:
			ideias.remover_ideia(int(ideia_id))
		except Exception:
			pass
		self._send(self.render_ideas_plans())

	def _responder_com_calendario(self, painel):
		cal_html = self.render_calendar(painel.year, painel.month, painel)
		cal_oob = cal_html.replace('id="calendar"', 'id="calendar" hx-swap-oob="true"', 1)
		self._send(self.render_day_panel(painel) + cal_oob)

	def _notificar_clientes(self):
		with self.sse_lock:
			for client in self.sse_clients[:]:
				try:
					client["write"]({"type": "refresh", "timestamp": time_module.time()})
				except Exception:
					self.sse_clients.remove(client)

	def log_message(self, *a):
		pass

import io
import json
import unittest
from datetime import date

import server
from inc.Handler import Handler
from inc.handler_logic import (
    build_nearby_events_payload,
    import_events,
    merge_event_update,
    parse_alerts_minutes,
    parse_event_form,
)


class DummyAgenda:
    FMT = "%Y-%m-%d %H:%M"
    GOOGLE_AVAILABLE = False
    GOOGLE_CREDENTIALS_FILE = type("P", (), {"exists": staticmethod(lambda: False)})()
    GOOGLE_TOKEN_FILE = type("P", (), {"exists": staticmethod(lambda: False), "unlink": staticmethod(lambda: None)})()

    def __init__(self):
        self.saved = None
        self.events = []

    def carregar(self):
        return list(self.events)

    def salvar(self, eventos):
        self.saved = list(eventos)
        self.events = list(eventos)

    def proximo_id(self, eventos):
        return max((e["id"] for e in eventos), default=0) + 1

    def expandir(self, eventos, inicio, fim):
        return []


class HandlerRefactorTests(unittest.TestCase):
    def setUp(self):
        self.original_agenda = Handler.agenda
        self.original_render_day_panel = Handler.render_day_panel
        self.original_render_calendar = Handler.render_calendar
        self.original_render_alerts_banner = Handler.render_alerts_banner
        self.original_render_proximos_eventos_dia = Handler.render_proximos_eventos_dia
        self.original_render_sync_status = Handler.render_sync_status
        self.original_load_config_template = Handler.load_config_template
        self.original_sse_clients = Handler.sse_clients
        self.original_sse_lock = Handler.sse_lock
        self.original_restart_state = Handler.restart_state
        self.original_server_instance = Handler.server_instance

        self.agenda = DummyAgenda()
        Handler.configure(
            agenda=self.agenda,
            render_day_panel=lambda painel, editando=None: f"day:{painel.isoformat() if hasattr(painel, 'isoformat') else painel}",
            render_calendar=lambda year, month, sel: f"calendar:{year}-{month}",
            render_alerts_banner=lambda: "banner",
            render_proximos_eventos_dia=lambda d: "next",
            render_sync_status=lambda msg, **kwargs: f"sync:{msg}",
            load_config_template=lambda: "config",
            sse_clients=[],
            sse_lock=__import__("threading").Lock(),
            restart_state={"value": False},
            server_instance={"value": None},
        )

    def tearDown(self):
        Handler.configure(
            agenda=self.original_agenda,
            render_day_panel=self.original_render_day_panel,
            render_calendar=self.original_render_calendar,
            render_alerts_banner=self.original_render_alerts_banner,
            render_proximos_eventos_dia=self.original_render_proximos_eventos_dia,
            render_sync_status=self.original_render_sync_status,
            load_config_template=self.original_load_config_template,
            sse_clients=self.original_sse_clients,
            sse_lock=self.original_sse_lock,
            restart_state=self.original_restart_state,
            server_instance=self.original_server_instance,
        )

    def _make_handler(self):
        handler = object.__new__(Handler)
        handler.wfile = io.BytesIO()
        handler.rfile = io.BytesIO()
        handler.headers = {}
        handler.responses = []
        handler.send_response = lambda status: handler.responses.append(("status", status))
        handler.send_header = lambda name, value: handler.responses.append((name, value))
        handler.end_headers = lambda: handler.responses.append(("end", None))
        return handler

    def test_parse_date_uses_fallback_when_invalid(self):
        handler = self._make_handler()
        self.assertEqual(handler._parse_date("invalid", date(2026, 8, 25)), date(2026, 8, 25))

    def test_importar_eventos_deduplicates_ids(self):
        handler = self._make_handler()
        payload = json.dumps([
            {"id": 1, "titulo": "Existente"},
            {"id": 2, "titulo": "Novo"},
        ])
        self.agenda.events = [{"id": 1, "titulo": "Base"}]

        handler._importar_eventos(payload)

        body = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertTrue(body["ok"])
        self.assertEqual(body["count"], 1)
        self.assertEqual([e["id"] for e in self.agenda.saved], [1, 2])

    def test_server_imports_same_handler_class(self):
        self.assertIs(server.Handler, Handler)


class HandlerLogicTests(unittest.TestCase):
    def test_parse_alerts_minutes_filters_and_sorts(self):
        self.assertEqual(parse_alerts_minutes("[15, 60, 0, -1, 30]"), [60, 30, 15])

    def test_build_nearby_events_payload_matches_markers(self):
        agora = __import__("datetime").datetime(2026, 8, 25, 10, 0)

        def carregar():
            return [{"id": 7, "titulo": "Reunião"}]

        def expandir(eventos, inicio, fim):
            return [(agora.__class__(2026, 8, 25, 11, 0), eventos[0])]

        payload = build_nearby_events_payload(carregar, expandir, agora, [60, 30])
        self.assertEqual(payload["eventos"], [{"titulo": "Reunião", "minutos_restantes": 60, "hora": "11:00", "id": 7}])

    def test_parse_event_form_normalizes_defaults(self):
        class AgendaStub:
            FMT = "%Y-%m-%d %H:%M"

        form = {"date": "2026-08-25", "titulo": "  Teste  ", "desc": "  nota  "}
        info = parse_event_form(form, AgendaStub(), lambda value: date.fromisoformat(value))
        self.assertEqual(info["titulo"], "Teste")
        self.assertEqual(info["desc"], "nota")
        self.assertEqual(info["dur"], None)
        self.assertEqual(info["repeat"], None)

    def test_merge_event_update_applies_status(self):
        class AgendaStub:
            FMT = "%Y-%m-%d %H:%M"

        evento = {"titulo": "Antes", "concluido": False, "cancelado": False}
        merge_event_update(evento, {"date": "2026-08-25", "status": "concluido", "titulo": "Depois"}, AgendaStub(), lambda value: date.fromisoformat(value))
        self.assertEqual(evento["titulo"], "Depois")
        self.assertTrue(evento["concluido"])
        self.assertFalse(evento["cancelado"])

    def test_import_events_skips_duplicates(self):
        existing = [{"id": 1, "titulo": "Base"}]
        incoming = [{"id": 1, "titulo": "Dup"}, {"id": 2, "titulo": "Novo"}]
        eventos, count = import_events(existing, incoming)
        self.assertEqual(count, 1)
        self.assertEqual([e["id"] for e in eventos], [1, 2])


if __name__ == "__main__":
    unittest.main()
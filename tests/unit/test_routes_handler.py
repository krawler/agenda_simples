import io
import json
import unittest
from datetime import date
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from inc.Handler import Handler


class DummyAgendaMinimal:
    FMT = "%Y-%m-%d %H:%M"
    GOOGLE_AVAILABLE = False
    GOOGLE_CREDENTIALS_FILE = type("P", (), {"exists": staticmethod(lambda: False)})()
    GOOGLE_TOKEN_FILE = type("P", (), {"exists": staticmethod(lambda: False), "unlink": staticmethod(lambda: None)})()

    def __init__(self):
        self.events = []

    def carregar(self):
        return list(self.events)

    def salvar(self, eventos):
        self.events = list(eventos)

    def proximo_id(self, eventos):
        return max((e["id"] for e in eventos), default=0) + 1

    def expandir(self, eventos, inicio, fim):
        return []


class RoutesHandlerTests(unittest.TestCase):
    def setUp(self):
        self.original_agenda = Handler.agenda
        Handler.configure(
            agenda=DummyAgendaMinimal(),
            render_day_panel=lambda painel, editando=None: f"day:{painel}",
            render_calendar=lambda y, m, sel: "cal",
            render_alerts_banner=lambda: "b",
            render_proximos_eventos_dia=lambda d: "n",
            render_sync_status=lambda msg, **k: f"sync:{msg}",
            load_config_template=lambda: "conf",
            sse_clients=[],
            sse_lock=__import__("threading").Lock(),
            restart_state={"value": False},
            server_instance={"value": None},
        )

    def tearDown(self):
        Handler.configure(agenda=self.original_agenda)

    def _make_handler(self, method="POST", path="/delete", body=b"", headers=None):
        h = object.__new__(Handler)
        h.wfile = io.BytesIO()
        h.rfile = io.BytesIO(body)
        h.headers = headers or {}
        h.path = path
        h.responses = []
        h.send_response = lambda status: h.responses.append(("status", status))
        h.send_header = lambda name, value: h.responses.append((name, value))
        h.end_headers = lambda: h.responses.append(("end", None))
        return h

    def test_post_delete_returns_calendar_fragment_and_updates_store(self):
        handler = self._make_handler(method="POST", path="/delete?id=1&date=2026-08-25", body=b"")
        # populate with an event
        Handler.agenda.events = [{"id": 1, "titulo": "X"}]
        handler.do_POST()
        body = handler.wfile.getvalue().decode("utf-8")
        self.assertIn("day:", body)
        self.assertEqual(Handler.agenda.events, [])

    def test_post_skip_adds_exception_and_returns_fragment(self):
        handler = self._make_handler(method="POST", path="/skip?id=2&date=2026-08-25", body=b"")
        Handler.agenda.events = [{"id": 2, "titulo": "Y", "except": []}]
        handler.do_POST()
        body = handler.wfile.getvalue().decode("utf-8")
        self.assertIn("day:", body)
        self.assertIn("2026-08-25", json.dumps(Handler.agenda.events))

    def test_get_delete_without_post_returns_404(self):
        handler = self._make_handler()
        handler.path = "/delete?id=1&date=2026-08-25"
        handler.do_GET()
        # GET /delete is not implemented so expect 404 response header
        statuses = [r for r in handler.responses if r[0] == "status"]
        self.assertTrue(any(s[1] == 404 for s in statuses))

    def test_get_img_asset_serves_png(self):
        handler = self._make_handler(method="GET", path="/img/icones_separados/agenda_azul.png")
        handler.do_GET()
        statuses = [r for r in handler.responses if r[0] == "status"]
        self.assertTrue(any(s[1] == 200 for s in statuses))
        self.assertIn(b"PNG", handler.wfile.getvalue()[:8])


if __name__ == "__main__":
    unittest.main()

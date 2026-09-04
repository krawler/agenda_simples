import io
import json
import unittest
from datetime import date
from pathlib import Path
import sys

import renderers


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
            render_period_view=lambda data, view="day": f"period:{view}:{data}",
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

    def test_get_agenda_period_view_returns_fragment(self):
        handler = self._make_handler(method="GET", path="/agenda?view=week&date=2026-08-25")
        handler.do_GET()
        body = handler.wfile.getvalue().decode("utf-8")
        self.assertIn("period:week:2026-08-25", body)

    def test_get_agenda_default_view_uses_day(self):
        handler = self._make_handler(method="GET", path="/agenda")
        handler.do_GET()
        body = handler.wfile.getvalue().decode("utf-8")
        self.assertIn("period:day:", body)

    def test_get_root_url_renders_page(self):
        handler = self._make_handler(method="GET", path="/")
        handler.do_GET()
        body = handler.wfile.getvalue().decode("utf-8")
        self.assertIn("calendar", body)
        self.assertNotIn("<h1>404</h1>", body)

    def test_root_uses_cookie_view_and_date_when_present(self):
        Handler.configure(
            agenda=DummyAgendaMinimal(),
            render_day_panel=lambda painel, editando=None: f"day:{painel}",
            render_calendar=lambda y, m, sel: "cal",
            render_period_view=lambda data, view="day": f"period:{view}:{data}",
            render_page=lambda sel, view="month": f"page:{view}:{sel}",
            render_alerts_banner=lambda: "b",
            render_proximos_eventos_dia=lambda d: "n",
            render_sync_status=lambda msg, **k: f"sync:{msg}",
            load_config_template=lambda: "conf",
            sse_clients=[],
            sse_lock=__import__("threading").Lock(),
            restart_state={"value": False},
            server_instance={"value": None},
        )
        handler = self._make_handler(method="GET", path="/", headers={"Cookie": "agenda_view=week; agenda_date=2026-08-25"})
        handler.do_GET()
        body = handler.wfile.getvalue().decode("utf-8")
        self.assertIn("page:week:2026-08-25", body)

    def test_move_sets_view_cookie_for_future_refreshes(self):
        handler = self._make_handler(method="POST", path="/move?id=1&date=2026-08-26&time=15:30&panel_date=2026-08-26&view=week")
        Handler.agenda.events = [{
            "id": 1,
            "titulo": "Reunião",
            "inicio": "2026-08-25 09:00",
            "dur": 60,
            "desc": "Descrição",
            "repeat": None,
            "until": None,
            "concluido": False,
            "cancelado": False,
        }]
        handler.do_POST()
        headers = [value for name, value in handler.responses if name == "Set-Cookie"]
        self.assertTrue(any("agenda_view=week" in str(value) for value in headers))
        self.assertTrue(any("agenda_date=2026-08-26" in str(value) for value in headers))

    def test_get_agenda_blank_date_defaults_to_today(self):
        handler = self._make_handler(method="GET", path="/agenda?view=day&date=")
        handler.do_GET()
        body = handler.wfile.getvalue().decode("utf-8")
        self.assertIn("period:day:", body)
        self.assertNotIn("<h1>404</h1>", body)

    def test_get_agenda_non_iso_date_defaults_to_today(self):
        handler = self._make_handler(method="GET", path="/agenda?view=day&date=20160903")
        handler.do_GET()
        body = handler.wfile.getvalue().decode("utf-8")
        self.assertIn("period:day:", body)
        self.assertNotIn("<h1>404</h1>", body)

    def test_render_period_view_day_has_timeline_layout(self):
        html = renderers.render_period_view(date(2026, 8, 25), view="day")
        self.assertIn('agenda-day-timeline', html)
        self.assertIn('agenda-hour-label', html)
        self.assertIn('agenda-hour-row', html)

    def test_render_period_view_day_has_hour_drop_targets(self):
        html = renderers.render_period_view(date(2026, 8, 25), view="day")
        self.assertIn('data-drop-hour="9"', html)
        self.assertIn('agenda-drop-zone', html)

    def test_render_period_view_day_has_drag_metadata(self):
        html = renderers.render_period_view(date(2026, 8, 25), view="day")
        self.assertIn('draggable="true"', html)
        self.assertIn('data-event-id', html)
        self.assertIn('data-drop-date', html)

    def test_render_period_view_day_groups_same_hour_events_in_shared_container(self):
        html = renderers.render_period_view(date(2026, 8, 25), view="day")
        self.assertIn('agenda-hour-events', html)
        self.assertIn('display: flex', html)

    def test_render_period_view_day_mark_confirms_drop_before_commit(self):
        html = renderers.render_period_view(date(2026, 8, 25), view="day")
        self.assertIn('confirmar-movimentacao', html)

    def test_post_move_event_updates_datetime(self):
        handler = self._make_handler(method="POST", path="/move?id=1&date=2026-08-26&time=15:30&panel_date=2026-08-26")
        Handler.agenda.events = [{
            "id": 1,
            "titulo": "Reunião",
            "inicio": "2026-08-25 09:00",
            "dur": 60,
            "desc": "Descrição",
            "repeat": None,
            "until": None,
            "concluido": False,
            "cancelado": False,
        }]
        handler.do_POST()
        body = handler.wfile.getvalue().decode("utf-8")
        self.assertIn("day:", body)
        self.assertEqual(Handler.agenda.events[0]["inicio"], "2026-08-26 15:30")


if __name__ == "__main__":
    unittest.main()

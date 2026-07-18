from __future__ import annotations

import unittest
from datetime import date
from unittest import mock

from monark_schedule import entry_key
from service_log import generate_service_log


class _FakeSessionState(dict):
    """Minimal stand-in for st.session_state attribute + item access."""

    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value) -> None:
        self[name] = value

    def __delattr__(self, name: str) -> None:
        try:
            del self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


class ServiceRowStagingTest(unittest.TestCase):
    def test_stage_reload_does_not_touch_widget_keys(self) -> None:
        import app as app_module

        entries = generate_service_log(2026)
        first_id = entry_key(entries[0])
        fake_state = _FakeSessionState(
            {
                "service_log_entries": entries,
                "simple_title_input": "OLD TITLE",
                "simple_speaker_input": "OLD SPEAKER",
            }
        )
        with mock.patch.object(app_module.st, "session_state", fake_state):
            app_module._stage_service_row_reload(first_id)
            self.assertEqual(fake_state["simple_title_input"], "OLD TITLE")
            self.assertEqual(fake_state["simple_speaker_input"], "OLD SPEAKER")
            self.assertTrue(fake_state["needs_input_reload"])
            self.assertEqual(fake_state["pending_title_input"], "")
            self.assertEqual(fake_state["pending_speaker_input"], "")
            self.assertEqual(fake_state["pending_service_row_id"], first_id)
            self.assertEqual(fake_state["pending_date_input"], date(2026, 7, 31))

    def test_apply_pending_loads_blank_row_into_widget_keys(self) -> None:
        import app as app_module

        fake_state = _FakeSessionState(
            {
                "needs_input_reload": True,
                "pending_title_input": "",
                "pending_speaker_input": "",
                "pending_notes_input": "keep notes pending",
                "pending_date_input": date(2026, 7, 31),
                "pending_service_input": "Morning",
                "pending_current_service_select": "2026-07-31_AM",
                "pending_service_row_id": "2026-07-31_AM",
                "simple_title_input": "STALE",
                "simple_speaker_input": "STALE",
            }
        )
        with mock.patch.object(app_module.st, "session_state", fake_state):
            app_module._apply_pending_input_values_before_widgets()
            self.assertEqual(fake_state["simple_title_input"], "")
            self.assertEqual(fake_state["simple_speaker_input"], "")
            self.assertEqual(fake_state["simple_date_input"], date(2026, 7, 31))
            self.assertEqual(fake_state["simple_service_select"], "Morning")
            self.assertEqual(fake_state["service_log_current_select"], "2026-07-31_AM")
            self.assertEqual(fake_state["service_log_selected_row_id"], "2026-07-31_AM")
            self.assertEqual(fake_state["selected_service_row_id"], "2026-07-31_AM")
            self.assertNotIn("needs_input_reload", fake_state)
            self.assertNotIn("pending_title_input", fake_state)

    def test_generate_stages_first_row_without_widget_mutation(self) -> None:
        import app as app_module

        fake_state = _FakeSessionState(
            {
                "service_log_entries": [],
                "service_log_confirm_replace": False,
                "service_log_year": 2026,
                "simple_title_input": "STALE",
                "simple_speaker_input": "STALE",
            }
        )
        with mock.patch.object(app_module.st, "session_state", fake_state), mock.patch.object(
            app_module, "save_service_log"
        ), mock.patch.object(app_module, "archive_service_log", return_value=None):
            app_module._generate_service_log(2026)
            self.assertEqual(len(fake_state["service_log_entries"]), 30)
            self.assertTrue(fake_state["needs_input_reload"])
            self.assertEqual(fake_state["simple_title_input"], "STALE")
            self.assertEqual(fake_state["pending_title_input"], "")
            self.assertTrue(
                str(fake_state["selected_service_row_id"]).endswith("_AM")
            )
            self.assertTrue(
                str(fake_state["service_log_selected_row_id"]).endswith("_AM")
            )

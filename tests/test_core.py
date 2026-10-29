"""Core behaviour that both shells depend on. Runs with or without a display."""

import os
import tempfile
import unittest
from unittest import mock

import vigia_core as core

SAMPLE = {
    "primary": "anthropic",
    "entries": [
        {"id": "openai", "name": "openai", "display_name": "Codex", "brand": "openai",
         "metrics": [{"label": "Codex 5h", "percent": 12, "headline": "percent"}]},
        {"id": "anthropic", "name": "anthropic", "display_name": "Claude", "brand": "anthropic",
         "metrics": [{"label": "Session", "percent": 24, "headline": "percent"}]},
        {"id": "opencode-go", "name": "opencode-go", "display_name": "OpenCode Go",
         "brand": "opencode-go",
         "metrics": [{"label": "Rolling", "percent": 41, "headline": "percent"}]},
    ],
}


class LanguageTests(unittest.TestCase):
    def test_every_language_has_the_same_keys(self):
        base = set(core.STRINGS["en"])
        for code, table in core.STRINGS.items():
            self.assertEqual(set(table), base, f"faltam chaves em {code}")

    def test_unknown_language_falls_back_to_english(self):
        self.assertEqual(core.translate("xx", "menu_size"), "Size")

    def test_placeholders(self):
        self.assertIn("Ctrl", core.translate("en", "hotkey_hint", accel="Ctrl"))


class AnchorTests(unittest.TestCase):
    AREA = (100, 50, 1000, 800)
    BOX = (200, 30)

    def position(self, anchor):
        return core.anchored_position(self.AREA, *self.BOX, anchor)

    def test_corners(self):
        self.assertEqual(self.position("top-left"), (118, 68))
        self.assertEqual(self.position("top-center"), (500, 68))
        self.assertEqual(self.position("top-right"), (882, 68))
        self.assertEqual(self.position("middle-left"), (118, 435))
        self.assertEqual(self.position("bottom-right"), (882, 802))

    def test_all_nine_stay_inside(self):
        for anchor in core.ANCHORS:
            x, y = self.position(anchor)
            self.assertGreaterEqual(x, self.AREA[0])
            self.assertGreaterEqual(y, self.AREA[1])
            self.assertLessEqual(x + self.BOX[0], self.AREA[0] + self.AREA[2])
            self.assertLessEqual(y + self.BOX[1], self.AREA[1] + self.AREA[3])


class ClampTests(unittest.TestCase):
    def test_outer_edge_may_sit_flush(self):
        x, _ = core.clamp_to_area(950, 0, 200, 30, (0, 0, 1000, 800), 18, (False, False, False, False))
        self.assertEqual(x, 800)

    def test_shared_edge_keeps_margin(self):
        x, _ = core.clamp_to_area(950, 0, 200, 30, (0, 0, 1000, 800), 18, (False, True, False, False))
        self.assertEqual(x, 782)

    def test_oversized_box_falls_back_to_area(self):
        x, _ = core.clamp_to_area(10, 0, 1200, 30, (0, 0, 1000, 800), 18, (False, True, False, False))
        self.assertEqual(x, 0)


class SeamTests(unittest.TestCase):
    MONITORS = [(0, 0, 1600, 900), (1600, 0, 1920, 1080)]

    def test_right_and_left(self):
        self.assertEqual(core.seam_edges(0, self.MONITORS), (False, True, False, False))
        self.assertEqual(core.seam_edges(1, self.MONITORS), (True, False, False, False))

    def test_single_monitor_has_no_seams(self):
        self.assertEqual(core.seam_edges(0, [(0, 0, 1920, 1080)]), (False, False, False, False))


class ConfigTests(unittest.TestCase):
    def test_roundtrip_and_sanitising(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "vigia.toml")
            with mock.patch.object(core, "LEGACY_CONFIG", os.path.join(directory, "missing.toml")):
                config = core.Config(path)
                config.set("opacity", 0.5)
                config.set("anchor", "bottom-right")
                config.set("language", "en")
                config.positions["screen"] = (12, 34)
                config.save()
                again = core.Config(path)
                self.assertEqual(again.get("opacity"), 0.5)
                self.assertEqual(again.get("anchor"), "bottom-right")
                self.assertEqual(again.get("language"), "en")
                self.assertEqual(again.positions["screen"], (12, 34))

    def test_metric_choices_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "vigia.toml")
            with mock.patch.object(core, "LEGACY_CONFIG", os.path.join(directory, "missing.toml")):
                config = core.Config(path)
                self.assertEqual(config.metric_choice("anthropic"), "auto")
                config.set_metric("Anthropic", "Weekly (7d)")
                config.set_metric("openai", "auto")
                self.assertEqual(config.metric_choice("anthropic"), "Weekly (7d)")
                self.assertEqual(config.metric_choice("openai"), "auto")
                again = core.Config(path)
                self.assertEqual(again.metric_choice("anthropic"), "Weekly (7d)")
                again.set_metric("anthropic", "auto")
                self.assertNotIn("anthropic", core.Config(path).metrics)

    def test_screen_names_are_valid_monitors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "vigia.toml")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write('[overlay]\nmonitor = "HDMI-A-0"\n')
            with mock.patch.object(core, "LEGACY_CONFIG", os.path.join(directory, "missing.toml")):
                config = core.Config(path)
            self.assertEqual(config.get("monitor"), "HDMI-A-0")

    def test_invalid_values_are_repaired(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "vigia.toml")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write('[overlay]\nopacity = 5.0\nsize = "huge"\nanchor = "nowhere"\nlanguage = "xx"\n')
            with mock.patch.object(core, "LEGACY_CONFIG", os.path.join(directory, "missing.toml")):
                config = core.Config(path)
            self.assertEqual(config.get("opacity"), 1.0)
            self.assertEqual(config.get("size"), "medium")
            self.assertEqual(config.get("anchor"), "top-right")
            self.assertEqual(config.get("language"), "auto")


class AlertTests(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(core.value_tint("alert", 59), core.TEXT_PRIMARY)
        self.assertEqual(core.value_tint("alert", 60), "#f2bd34")
        self.assertEqual(core.value_tint("alert", 80), "#ed4b48")
        self.assertEqual(core.value_tint("brand", 99), core.TEXT_PRIMARY)
        self.assertEqual(core.value_tint("alert", 30, warn=20, critical=25), "#ed4b48")

    def test_hidden_lists_are_normalised(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "vigia.toml")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write('[overlay]\nhide_providers = " OpenAI , openai ,, OPENCODE-GO "\n'
                             'hide_system = "CPU, gpu"\n')
            with mock.patch.object(core, "LEGACY_CONFIG", os.path.join(directory, "missing.toml")):
                config = core.Config(path)
            self.assertEqual(config.get("hide_providers"), "openai,opencode-go")
            self.assertEqual(config.get("hide_system"), "cpu,gpu")


class ProviderTests(unittest.TestCase):
    def test_rows_follow_report_order_and_limit(self):
        rows = core.provider_rows(SAMPLE, limit=2)
        self.assertEqual([row["name"] for row in rows], ["Claude", "Codex"])
        self.assertEqual(rows[0]["value"], "24%")

    def test_summary_prefers_quota_metric(self):
        entry = {"metrics": [{"percent": 10, "group": "sessions"}, {"percent": 70}]}
        self.assertEqual(core.summary_metric(entry)["percent"], 70)

    def test_pick_metric_follows_the_chosen_label(self):
        entry = {"metrics": [
            {"label": "Session (5h)", "percent": 4},
            {"label": "Weekly (7d)", "percent": 57},
            {"label": "Fable (7d)", "percent": 100},
        ]}
        self.assertEqual(core.pick_metric(entry)["label"], "Fable (7d)")
        self.assertEqual(core.pick_metric(entry, "Weekly (7d)")["label"], "Weekly (7d)")
        self.assertEqual(core.pick_metric(entry, "weekly 7D")["label"], "Weekly (7d)")

    def test_pick_metric_falls_back_when_the_label_is_gone(self):
        entry = {"metrics": [{"label": "Session (5h)", "percent": 4},
                             {"label": "Weekly (7d)", "percent": 57}]}
        self.assertEqual(core.pick_metric(entry, "Fable (7d)")["label"], "Weekly (7d)")
        self.assertIsNone(core.matching_metric(entry, "Fable (7d)"))

    def test_rows_use_the_configured_metric(self):
        report = {"entries": [{"id": "anthropic", "brand": "anthropic", "display_name": "Claude",
                               "metrics": [{"label": "Session (5h)", "percent": 4},
                                           {"label": "Weekly (7d)", "percent": 57}]}]}
        auto = core.provider_rows(report)
        chosen = core.provider_rows(report, choices={"anthropic": "Session (5h)"})
        self.assertEqual(auto[0]["value"], "57%")
        self.assertEqual(chosen[0]["value"], "4%")
        self.assertEqual(chosen[0]["label"], "Session (5h)")

    def test_value_headline_is_used_verbatim(self):
        self.assertEqual(core.metric_display({"headline": "value", "value": "$3.20"}), "$3.20")

    def test_installed_binary_override(self):
        self.assertEqual(core.installed_binary("ai-usagebar", override="/tmp/x"), "/tmp/x")

    def test_icon_lookup(self):
        icons = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icons")
        with mock.patch.dict(os.environ, {"VIGIA_ICON_DIR": icons}):
            self.assertTrue(core.icon_path("anthropic").endswith("claude.svg"))
            self.assertIsNone(core.icon_path("unknown-vendor"))


if __name__ == "__main__":
    unittest.main()

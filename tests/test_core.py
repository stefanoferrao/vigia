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

    def test_island_is_centred_and_clamped(self):
        area = (100, 50, 1000, 800)
        self.assertEqual(core.island_x(area, 120), 540)
        self.assertEqual(core.island_x(area, 120, 100), 640)
        self.assertEqual(core.island_x(area, 120, -9999), 100)
        self.assertEqual(core.island_x(area, 120, 9999), 980)

    def test_island_docks_to_every_edge(self):
        area = (100, 50, 1000, 800)
        self.assertEqual(core.island_position(area, "top-center", 120, 8), (540, 50))
        self.assertEqual(core.island_position(area, "bottom-right", 200, 26), (900, 824))
        self.assertEqual(core.island_position(area, "left-middle", 200, 26), (100, 437))
        self.assertEqual(core.island_position(area, "right-top", 8, 120, 40), (1092, 90))
        self.assertEqual(core.island_position(area, "left-bottom", 200, 26, 9999), (100, 824))
        self.assertEqual(core.island_position(area, "top-left", 200, 26, -500), (100, 50))
        self.assertEqual(len(core.ISLAND_ANCHORS), 12)

    def test_usagebar_asset_per_platform(self):
        self.assertEqual(core.usagebar_asset("Linux", "x86_64"), ("ai-usagebar-linux-x86_64.tar.gz", "tar"))
        self.assertEqual(core.usagebar_asset("Linux", "arm64"), ("ai-usagebar-linux-aarch64.tar.gz", "tar"))
        self.assertEqual(core.usagebar_asset("Windows", "AMD64"), ("ai-usagebar-windows-x86_64.exe", "exe"))
        self.assertIsNone(core.usagebar_asset("Linux", "riscv64"))

    def test_sha256_file_parsing(self):
        digest = "ab" * 32
        self.assertEqual(core.parse_sha256(f"{digest}  ai-usagebar-linux-x86_64.tar.gz\n"), digest)
        self.assertIsNone(core.parse_sha256("not a hash"))

    def test_ensure_usagebar_verifies_and_installs(self):
        import hashlib, io, tarfile, tempfile
        payload = b"#!/bin/sh\necho ai-usagebar 9.9.9\n"
        raw = io.BytesIO()
        with tarfile.open(fileobj=raw, mode="w:gz") as archive:
            info = tarfile.TarInfo("./ai-usagebar")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        blob = raw.getvalue()
        good = hashlib.sha256(blob).hexdigest().encode()
        from unittest import mock
        with tempfile.TemporaryDirectory() as home, \
                mock.patch.object(core, "HOME", home), \
                mock.patch.object(core, "usagebar_asset", return_value=("x.tar.gz", "tar")):
            bad = core.ensure_usagebar(fetch=lambda url: blob if url.endswith(".gz") else b"0" * 64)
            self.assertIsNone(bad)  # checksum mismatch: nothing is written
            path = core.ensure_usagebar(fetch=lambda url: blob if url.endswith(".gz") else good)
            self.assertTrue(path and open(path, "rb").read() == payload)

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
    def test_island_offsets_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "vigia.toml")
            with mock.patch.object(core, "LEGACY_CONFIG", os.path.join(directory, "missing.toml")):
                config = core.Config(path)
                self.assertFalse(config.get("island"))
                self.assertEqual(config.island_offsets, {})
                config.island_offsets["HDMI-A-0"] = -40
                config.save()
                again = core.Config(path)
                self.assertEqual(again.island_offsets["HDMI-A-0"], -40)
                self.assertFalse(again.get("island"))

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


class LocaleDetectionTests(unittest.TestCase):
    def test_locale_code(self):
        self.assertEqual(core.locale_code("pt_BR.UTF-8"), "pt")
        self.assertEqual(core.locale_code("pt_BR:pt:en"), "pt")
        self.assertEqual(core.locale_code("xx_XX:de_DE"), "de")
        self.assertEqual(core.locale_code("C.UTF-8"), None)
        self.assertEqual(core.locale_code(""), None)

    def test_system_language_reads_environment(self):
        env = {"LC_ALL": "", "LC_MESSAGES": "", "LANG": "fr_FR.UTF-8", "LANGUAGE": ""}
        with mock.patch.dict(os.environ, env):
            self.assertEqual(core.system_language(), "fr")

    def test_explicit_choice_beats_system(self):
        with tempfile.TemporaryDirectory() as directory:
            config = core.Config(os.path.join(directory, "vigia.toml"))
            config.values["language"] = "de"
            with mock.patch.dict(os.environ, {"LANG": "pt_BR.UTF-8"}):
                self.assertEqual(config.language(), "de")
                config.values["language"] = "auto"
                self.assertEqual(config.language(), "pt")


class AlertTests(unittest.TestCase):
    def test_thresholds(self):
        core.set_theme(core.THEME_DEFAULT)
        ok, warning, critical = (core.THEME[k] for k in ("state-ok", "state-warning", "state-critical"))
        self.assertEqual(core.value_tint("alert", 59), ok)
        self.assertEqual(core.value_tint("alert", 60), warning)
        self.assertEqual(core.value_tint("alert", 80), critical)
        self.assertEqual(core.value_tint("brand", 99), core.THEME["text-primary"])
        self.assertEqual(core.value_tint("alert", 30, warn=20, critical=25), critical)

    def test_bar_and_critical(self):
        core.set_theme(core.THEME_DEFAULT)
        self.assertEqual(core.bar_tint("alert", 90), core.THEME["state-critical"])
        self.assertEqual(core.bar_tint("brand", 90), core.THEME["primary"])
        self.assertEqual(core.bar_tint("alert", None), core.THEME["primary"])
        self.assertTrue(core.is_critical("alert", 80))
        self.assertFalse(core.is_critical("alert", 79))
        self.assertFalse(core.is_critical("brand", 99))

    def test_accent_overrides_primary(self):
        core.set_theme("light", accent="#ff00aa")
        self.assertEqual(core.THEME["primary"], "#ff00aa")
        core.set_theme("light", accent="not-a-colour")
        self.assertEqual(core.THEME["primary"], "#0066cc")

    def test_themes_load_and_fall_back(self):
        names = dict(core.list_themes())
        self.assertIn(core.THEME_DEFAULT, names)
        self.assertIn("light", names)
        core.set_theme("light")
        self.assertEqual(core.THEME["surface"], "#fafafa")
        core.set_theme("auto", dark=False)
        self.assertEqual(core.THEME["surface"], "#fafafa")
        core.set_theme("does-not-exist")
        self.assertEqual(core.THEME, core.THEME_FALLBACK)

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

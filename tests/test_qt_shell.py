"""Qt shell smoke tests. Skipped when PySide6 is not installed."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REQUIRE_QT = os.environ.get("VIGIA_REQUIRE_QT") == "1"

try:
    from PySide6.QtWidgets import QApplication
    import vigia_qt
    HAVE_QT = True
except Exception as error:  # pragma: no cover - environment without PySide6
    if REQUIRE_QT:
        raise
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, "PySide6 indisponível")
class AcceleratorTests(unittest.TestCase):
    def test_angle_and_plus_syntax(self):
        self.assertEqual(vigia_qt.parse_accelerator("<Control><Alt>u"), ({"control", "alt"}, "u"))
        self.assertEqual(vigia_qt.parse_accelerator("Control+Alt+u"), ({"control", "alt"}, "u"))
        self.assertEqual(vigia_qt.parse_accelerator("<Super><Shift>a"), ({"super", "shift"}, "a"))


@unittest.skipUnless(HAVE_QT, "PySide6 indisponível")
class RenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_provider_icon_renders(self):
        pixmap = vigia_qt.provider_pixmap("anthropic", "#d97757", 12, 1.0)
        self.assertIsNotNone(pixmap)
        self.assertFalse(pixmap.isNull())
        self.assertGreater(pixmap.width(), 0)

    def test_gear_renders(self):
        pixmap = vigia_qt.gear_pixmap(12, 1.0)
        self.assertIsNotNone(pixmap)
        self.assertFalse(pixmap.isNull())


@unittest.skipUnless(HAVE_QT, "PySide6 indisponível")
class StickyMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def build(self):
        root = vigia_qt.StickyMenu()
        root.setTitle("VigIA")
        sub = vigia_qt.StickyMenu(parent=root)
        sub.setTitle("Tamanho")
        root.addMenu(sub)
        return root, sub

    def test_submenu_stays_open_after_a_choice(self):
        root, sub = self.build()
        hits = []
        action = sub.addAction("Grande")
        action.triggered.connect(lambda: hits.append(True))
        root.show()
        sub.show()
        try:
            self.assertTrue(sub._activate(action))
            self.assertEqual(hits, [True])
            self.assertTrue(sub.isVisible(), "submenu fechou sozinho")
            self.assertTrue(root.isVisible(), "menu raiz fechou junto")
        finally:
            sub.hide()
            root.hide()

    def test_closes_menu_action_hides_the_whole_chain(self):
        root, sub = self.build()
        action = sub.addAction("Sair")
        action.setProperty("closes_menu", True)
        root.show()
        sub.show()
        try:
            self.assertTrue(sub._activate(action))
            self.assertFalse(sub.isVisible())
            self.assertFalse(root.isVisible())
        finally:
            sub.hide()
            root.hide()


if __name__ == "__main__":
    unittest.main()

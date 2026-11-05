import tempfile
import unittest
from pathlib import Path

from service.api import static


class StaticTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_no_build_returns_none(self) -> None:
        self.assertIsNone(static.load("/", root=self.tmp / "missing"))

    def test_missing_index_returns_none(self) -> None:
        self.assertIsNone(static.load("/anything", root=self.tmp))

    def test_serves_index_and_assets(self) -> None:
        (self.tmp / "index.html").write_text("<html>hi</html>")
        (self.tmp / "assets").mkdir()
        (self.tmp / "assets" / "app.js").write_text("x=1")
        found = static.load("/", root=self.tmp)
        assert found is not None
        self.assertEqual(found, (b"<html>hi</html>", "text/html"))
        found = static.load("/assets/app.js", root=self.tmp)
        assert found is not None
        self.assertEqual(found[0], b"x=1")
        self.assertIn("javascript", found[1])

    def test_unknown_path_falls_back_to_index(self) -> None:
        (self.tmp / "index.html").write_text("<html>hi</html>")
        found = static.load("/play", root=self.tmp)
        assert found is not None
        self.assertEqual(found[0], b"<html>hi</html>")

    def test_path_traversal_blocked(self) -> None:
        root = self.tmp / "dist"
        root.mkdir()
        (root / "index.html").write_text("<html>hi</html>")
        (self.tmp / "secret.txt").write_text("secret")
        found = static.load("/../secret.txt", root=root)
        assert found is not None
        self.assertEqual(found[0], b"<html>hi</html>")


if __name__ == "__main__":
    unittest.main()

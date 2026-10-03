import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import data_paths


class TestDataPaths(unittest.TestCase):
    def test_data_path_uses_data_folder(self):
        path = data_paths.resolve_data_path("eventos.json")
        normalized = os.path.normpath(str(path))
        self.assertTrue(normalized.endswith(os.path.join("data", "eventos.json")))

    def test_data_path_migrates_legacy_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "eventos.json"
            legacy.write_text('[]', encoding="utf-8")

            old_root = data_paths.ROOT
            old_data_dir = data_paths.DATA_DIR
            try:
                data_paths.ROOT = root
                data_paths.DATA_DIR = root / "data"
                path = data_paths.resolve_data_path("eventos.json")
                self.assertTrue(path.exists())
                self.assertEqual(path.read_text(encoding="utf-8"), "[]")
            finally:
                data_paths.ROOT = old_root
                data_paths.DATA_DIR = old_data_dir


if __name__ == "__main__":
    unittest.main()

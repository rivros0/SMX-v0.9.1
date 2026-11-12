"""Test isolati del launcher; nessuna connessione o download richiesti."""

import json
from pathlib import Path
import tempfile
import unittest

from smx_launcher import (
    expected_sha256,
    restore_previous,
    safe_member_path,
    version_sort_key,
)


class LauncherTests(unittest.TestCase):
    def test_numeric_version_order(self):
        self.assertGreater(version_sort_key("v0.10.0"), version_sort_key("v0.9.9"))
        self.assertEqual(version_sort_key("v1.2.3"), (1, 2, 3))

    def test_manifest_checksum_lookup(self):
        digest = "a" * 64
        data = "{}  SMX-linux-x64.tar.gz\n".format(digest)
        self.assertEqual(
            expected_sha256(data, "SMX-linux-x64.tar.gz"),
            digest,
        )

    def test_rejects_parent_directory_traversal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaises(RuntimeError):
                safe_member_path(root, "../../outside.txt")

    def test_rejects_absolute_path(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaises(RuntimeError):
                safe_member_path(root, "/tmp/outside.txt")

    def test_rejects_windows_drive(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaises(RuntimeError):
                safe_member_path(root, "C:/windows/system.ini")

    def test_normal_archive_path(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            candidate = safe_member_path(root, "SMX/lib/library.dll")
            self.assertEqual(candidate, root / "SMX" / "lib" / "library.dll")

    def test_manual_restore_preserves_current_as_previous(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            if __import__("sys").platform == "win32":
                binary = root / "versions" / "v1.0.0" / "SMX" / "SMX.exe"
            else:
                binary = root / "versions" / "v1.0.0" / "SMX" / "SMX"
            binary.parent.mkdir(parents=True, exist_ok=True)
            binary.write_bytes(b"dummy")
            marker = root / "current.json"
            marker.write_text(
                json.dumps({"version": "v1.1.0", "previous": "v1.0.0"}),
                encoding="utf-8",
            )
            restored = restore_previous(root)
            self.assertEqual(restored, "v1.0.0")
            manifest = json.loads(marker.read_text(encoding="utf-8"))
            self.assertEqual(manifest["previous"], "v1.1.0")


if __name__ == "__main__":
    unittest.main()

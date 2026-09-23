"""Persistence and source-preservation tests; visual curation requires separate review."""
import base64
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
import threading
import unittest
from uuid import uuid4
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zlib

SPEC = importlib.util.spec_from_file_location("moodboard", Path(__file__).resolve().parents[1] / "moodboard.py")
mb = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mb)


def png(width, height, color=(31, 70, 50, 255)):
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
    raw = (b"\0" + bytes(color) * width) * height
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


class MoodboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.export_png = "data:image/png;base64," + base64.b64encode(png(2000, 400)).decode()

    def setUp(self):
        self.base = Path(os.environ.get("MOODBOARD_TEST_ROOT", tempfile.gettempdir())).resolve()
        self.root = self.base / ("moodboard-tests-" + uuid4().hex)
        self.root.mkdir(parents=True)
        self.model = mb.init_board(self.root, "design/art/moodboards/theme", "Art Direction.md", "theme", "game-theme", "主题方向", None)
        original = png(10, 12)
        self.original = original
        board, _ = self.model.read()
        board["references"] = [{"id": "r1", "file": mb.keep_image(self.model.folder, original), "title": "参考一", "note": "轮廓关系", "exclude": "具体身份", "sourceLabel": "测试图", "sourceUrl": "", "usage": "程序生成的保存测试输入", "role": "primary", "viewed": True}]
        board["direction"]["feeling"] = "温暖"
        board["palette"][0]["hex"] = "#123456"
        mb.atomic(self.model.current, mb.encoded(board))
        mb.write_bootstrap(self.model.folder, board)
        self.model.document.write_text("# 项目美术\n\n保留用户的角色说明。\n", encoding="utf-8")

    def tearDown(self):
        if self.root.resolve().parent != self.base or not self.root.name.startswith("moodboard-tests-"):
            raise ValueError("Refusing cleanup outside the test root")
        shutil.rmtree(self.root)

    def payload(self):
        board, expected = self.model.read()
        board["revision"] += 1
        return {"board": board, "expected": expected, "png": self.export_png}

    def test_save_versions_keep_sources_palette_and_unrelated_document(self):
        first = self.model.save(self.payload())
        self.assertEqual(first["board"]["palette"][0]["hex"], "#123456")
        self.assertEqual(first["board"]["status"], "candidate")
        self.assertEqual(self.model.document.read_text(encoding="utf-8").count("保留用户的角色说明。"), 1)
        self.assertEqual((self.model.folder / first["board"]["references"][0]["file"]).read_bytes(), self.original)
        snapshot = (self.model.folder / first["config"]).read_bytes()
        payload = self.payload()
        payload["board"]["palette"][1]["hex"] = "#FEDCBA"
        second = self.model.save(payload)
        self.assertEqual(second["board"]["revision"], 2)
        self.assertEqual((self.model.folder / first["config"]).read_bytes(), snapshot)
        document = self.model.document.read_text(encoding="utf-8")
        self.assertEqual(document.count("<!-- moodboard:theme:start -->"), 1)
        self.assertIn(second["png"], document)
        self.assertNotIn(first["png"], document)

    def test_embedded_upload_becomes_local_immutable_source(self):
        payload = self.payload()
        ref = payload["board"]["references"][0]
        ref.pop("file")
        ref["data"] = "data:image/png;base64," + base64.b64encode(png(18, 8)).decode()
        saved = self.model.save(payload)
        ref = saved["board"]["references"][0]
        self.assertNotIn("data", ref)
        self.assertTrue((self.model.folder / ref["file"]).exists())
        self.assertIn("data:image/png;base64,", (self.model.folder / "board-data.js").read_text(encoding="utf-8"))

    def test_unviewed_and_support_only_are_not_exported(self):
        for change in ({"viewed": False}, {"role": "supporting"}):
            payload = self.payload()
            payload["board"]["references"][0].update(change)
            with self.assertRaises(ValueError):
                self.model.save(payload)
        self.assertFalse((self.model.folder / "versions").exists())

    def test_conflict_does_not_overwrite_newer_saved_board(self):
        stale = self.payload()
        first = self.model.save(self.payload())
        document = self.model.document.read_bytes()
        with self.assertRaisesRegex(ValueError, "磁盘图板已变化"):
            self.model.save(stale)
        self.assertEqual(self.model.document.read_bytes(), document)
        self.assertEqual(self.model.read()[0], first["board"])

    def test_identity_palette_and_selection_validation(self):
        for change in ({"id": "other"}, {"scope": "asset", "assetId": "courier"}, {"status": "selected", "selectionBasis": ""}):
            payload = self.payload()
            payload["board"].update(change)
            with self.assertRaises(ValueError):
                self.model.save(payload)
        payload = self.payload()
        payload["board"]["palette"][0]["hex"] = "#ZZZZZZ"
        with self.assertRaises(ValueError):
            self.model.save(payload)

    def test_replaced_source_and_missing_source_fail_without_doc_write(self):
        payload = self.payload()
        payload["board"]["references"][0]["file"] = "../../../../outside.png"
        before = self.model.document.read_bytes()
        with self.assertRaises(ValueError):
            self.model.save(payload)
        payload["board"]["references"][0]["file"] = "missing.png"
        with self.assertRaises(ValueError):
            self.model.save(payload)
        self.assertEqual(self.model.document.read_bytes(), before)

    def test_png_corruption_is_not_saved(self):
        raw = bytearray(png(2000, 400))
        raw[-6] ^= 1
        payload = self.payload()
        payload["png"] = "data:image/png;base64," + base64.b64encode(raw).decode()
        with self.assertRaises(ValueError):
            self.model.save(payload)
        self.assertFalse((self.model.folder / "versions").exists())

    def test_modified_saved_original_is_detected(self):
        saved = self.model.save(self.payload())
        path = self.model.folder / saved["board"]["references"][0]["file"]
        path.write_bytes(png(10, 12, (200, 10, 10, 255)))
        with self.assertRaisesRegex(ValueError, "校验值不同"):
            self.model.read()

    def test_document_markers_and_lock_are_respected(self):
        self.model.document.write_text("用户文字\n<!-- moodboard:theme:start -->", encoding="utf-8")
        before = self.model.document.read_bytes()
        with self.assertRaises(ValueError):
            self.model.save(self.payload())
        self.assertEqual(self.model.document.read_bytes(), before)
        lock = self.root / ".moodboard-write.lock"
        lock.write_text("another writer")
        with self.assertRaises(ValueError):
            self.model.save(self.payload())
        self.assertTrue(lock.exists())

    def test_failure_after_document_write_restores_previous_state(self):
        before_doc, before_board = self.model.document.read_bytes(), self.model.current.read_bytes()
        real_atomic = mb.atomic
        def failing(path, data):
            if path == self.model.current:
                raise OSError("simulated storage failure")
            return real_atomic(path, data)
        with patch.object(mb, "atomic", side_effect=failing):
            with self.assertRaises(OSError):
                self.model.save(self.payload())
        self.assertEqual(self.model.document.read_bytes(), before_doc)
        self.assertEqual(self.model.current.read_bytes(), before_board)
        receipts = list((self.model.folder / "versions").glob("*/receipt.json"))
        self.assertEqual(json.loads(receipts[0].read_bytes())["status"], "failed")

    def test_asset_parent_warning_does_not_mutate_asset(self):
        asset = mb.init_board(self.root, "design/art/moodboards/courier", "Art Direction.md", "courier", "asset", "角色", "courier")
        board, _ = asset.read()
        board["parent"] = {"id": "theme", "revision": 0}
        mb.atomic(asset.current, mb.encoded(board))
        before = asset.current.read_bytes()
        result = self.model.save(self.payload())
        self.assertTrue(any("courier" in item for item in result["warnings"]))
        self.assertTrue(any("theme" in item for item in asset.warnings(board)))
        self.assertEqual(asset.current.read_bytes(), before)

    def test_relocation_and_custom_art_direction_path(self):
        self.model.save(self.payload())
        moved = self.root / "移动后的项目"
        shutil.copytree(self.root / "design", moved / "design")
        moved.mkdir(exist_ok=True)
        shutil.copy2(self.model.document, moved / "Art Direction.md")
        relocated = mb.ProjectBoard(moved, "design/art/moodboards/theme")
        self.assertEqual(relocated.read()[0]["palette"][0]["hex"], "#123456")
        relocated.document = moved / "docs" / "美术 方向.md"
        payload = {"board": deepcopy(relocated.read()[0]), "expected": relocated.read()[1], "png": self.export_png}
        payload["board"]["revision"] += 1
        relocated.save(payload)
        self.assertIn("../design/art/moodboards/theme/versions/", relocated.document.read_text(encoding="utf-8"))

    def test_read_only_http_does_not_serve_project_files_or_receipts(self):
        server = mb.make_server(self.model)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(base + "/api/board") as response:
                self.assertEqual(json.load(response)["board"]["id"], "theme")
            for target in ("/../Art%20Direction.md", "/versions/fake/receipt.json"):
                with self.assertRaises(HTTPError):
                    urlopen(base + target)
            request = Request(base + "/api/export", data=b"{}", headers={"Content-Type": "application/json"})
            with self.assertRaises(HTTPError) as error:
                urlopen(request)
            self.assertEqual(error.exception.code, 403)
        finally:
            server.shutdown()
            server.server_close()
            worker.join()


if __name__ == "__main__":
    unittest.main()

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from packreceipt.core import ReceiptError, SCHEMA, compare, load_manifest, scan, validate_manifest
from packreceipt.__main__ import main
from packreceipt.report import render


def manifest(entries, label="folder"):
    return {"schema": SCHEMA, "algorithm": "sha256", "label": label, "files": [
        {"path": path, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        for path, content in entries
    ]}


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = self.base / "交付"
        self.root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def invoke(self, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = main(args)
        return code, output.getvalue()

    def test_scan_unicode_zero_and_nested_files(self):
        (self.root / "海报").mkdir()
        (self.root / "海报" / "初稿.txt").write_bytes(b"abc")
        (self.root / "empty").write_bytes(b"")
        result = scan(self.root)
        self.assertEqual(result["label"], "交付")
        self.assertEqual([x["path"] for x in result["files"]], ["empty", "海报/初稿.txt"])
        self.assertEqual(result["files"][1]["sha256"], hashlib.sha256(b"abc").hexdigest())
        self.assertNotIn(str(self.base), json.dumps(result, ensure_ascii=False))
        validate_manifest(result)

    def test_scan_empty_folder(self):
        self.assertEqual(scan(self.root)["files"], [])

    def test_scan_does_not_modify_content(self):
        path = self.root / "source.bin"
        path.write_bytes(bytes(range(256)))
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        scan(self.root)
        self.assertEqual(before, (path.read_bytes(), path.stat().st_mtime_ns))

    def test_scan_streams_file_larger_than_chunk(self):
        data = b"1234567890" * 220000
        (self.root / "large.bin").write_bytes(data)
        self.assertEqual(scan(self.root)["files"][0]["sha256"], hashlib.sha256(data).hexdigest())

    def test_reject_symlink_or_windows_junction(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "private.txt").write_text("not delivery", encoding="utf-8")
        link = self.root / "external"
        if os.name == "nt":
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            link.symlink_to(outside, target_is_directory=True)
        try:
            with self.assertRaisesRegex(ReceiptError, "reparse points"):
                scan(self.root)
        finally:
            if os.name == "nt":
                os.rmdir(link)
            else:
                link.unlink()
        self.assertTrue((outside / "private.txt").is_file())

    def test_detect_file_modified_during_hash(self):
        path = self.root / "busy.txt"
        path.write_bytes(b"start")
        real = hashlib.sha256

        class EditingHash:
            def __init__(self):
                self.value = real()

            def update(self, chunk):
                self.value.update(chunk)
                path.write_bytes(b"changed while reading")

            def hexdigest(self):
                return self.value.hexdigest()

        with patch("packreceipt.core.hashlib.sha256", EditingHash):
            with self.assertRaisesRegex(ReceiptError, "changed during scan"):
                scan(self.root)

    def test_compare_all_statuses(self):
        before = manifest([("same", b"s"), ("edit", b"a"), ("old/name", b"move"), ("gone", b"g")])
        after = manifest([("same", b"s"), ("edit", b"b"), ("new/name", b"move"), ("new", b"n")])
        result = compare(before, after)
        self.assertEqual(result["counts"], {"modified": 1, "moved": 1, "added": 1, "removed": 1, "unchanged": 1})
        self.assertFalse(result["matches"])

    def test_duplicate_content_does_not_invent_move(self):
        result = compare(manifest([("a", b"x"), ("b", b"x")]), manifest([("c", b"x")]))
        self.assertEqual(result["counts"]["moved"], 0)
        self.assertEqual(result["counts"]["removed"], 2)
        self.assertEqual(result["counts"]["added"], 1)
        self.assertEqual(result["ambiguous_content_groups"][0]["removed"], ["a", "b"])

    def test_same_path_takes_precedence_over_content_matching(self):
        result = compare(manifest([("a", b"x")]), manifest([("a", b"y"), ("b", b"x")]))
        self.assertEqual(result["counts"]["modified"], 1)
        self.assertEqual(result["counts"]["added"], 1)
        self.assertEqual(result["counts"]["moved"], 0)

    def test_changed_bytes_with_same_size_and_mtime_are_detected(self):
        path = self.root / "same-size"
        path.write_bytes(b"aaa")
        timestamp = path.stat().st_mtime_ns
        before = scan(self.root)
        path.write_bytes(b"bbb")
        os.utime(path, ns=(timestamp, timestamp))
        self.assertEqual(compare(before, scan(self.root))["counts"]["modified"], 1)

    def test_manifest_order_does_not_change_equality(self):
        first = manifest([("a", b"a"), ("b", b"b")])
        other = manifest([("b", b"b"), ("a", b"a")], label="renamed folder")
        self.assertTrue(compare(first, other)["matches"])

    def test_reject_invalid_external_manifest_paths(self):
        for path in ("", "/root", "../x", "a/../b", "a//b", "./a", "C:/x", "C:x", "a\\b", "a/", "a\x00b"):
            with self.subTest(path=path), self.assertRaises(ReceiptError):
                validate_manifest(manifest([(path, b"x")]))

    def test_reject_bad_digest_size_schema_and_duplicate(self):
        valid = manifest([("a", b"a")])
        for change in ({"size": -1}, {"size": True}, {"sha256": "0" * 63}, {"sha256": "X" * 64}):
            value = manifest([("a", b"a")])
            value["files"][0].update(change)
            with self.subTest(change=change), self.assertRaises(ReceiptError):
                validate_manifest(value)
        with self.assertRaises(ReceiptError):
            validate_manifest({**valid, "schema": "unknown"})
        with self.assertRaises(ReceiptError):
            validate_manifest(manifest([("a", b"x"), ("a", b"y")]))
        with self.assertRaises(ReceiptError):
            validate_manifest(manifest([("a", b"x"), ("a/b", b"y")]))

    def test_load_bom_and_invalid_json(self):
        path = self.base / "manifest.json"
        path.write_text(json.dumps(manifest([])), encoding="utf-8-sig")
        self.assertEqual(load_manifest(path)["files"], [])
        path.write_text("{broken", encoding="utf-8")
        with self.assertRaisesRegex(ReceiptError, "JSON"):
            load_manifest(path)

    def test_html_escapes_names_and_has_no_remote_resources(self):
        value = manifest([('<img src=x onerror=alert(1)>.txt', b"x")], label='</title><script>alert(1)</script>')
        output = render(compare(value, value), "zh")
        self.assertIn("&lt;img", output)
        self.assertNotIn("<img src=x", output)
        self.assertNotIn("<script>alert(1)", output)
        self.assertIn("Content-Security-Policy", output)
        self.assertNotIn("https://", output)
        self.assertNotIn("<script src=", output)

    def test_cli_verify_good_bad_and_path_change_exit_codes(self):
        (self.root / "file.txt").write_bytes(b"expected")
        saved = self.base / "receipt.json"
        self.assertEqual(self.invoke(["scan", str(self.root), "--out", str(saved)])[0], 0)
        html = self.base / "report.html"
        command = ["verify", str(saved), str(self.root), "--html", str(html)]
        self.assertEqual(self.invoke(command)[0], 0)
        (self.root / "file.txt").rename(self.root / "renamed.txt")
        self.assertEqual(self.invoke(command + ["--force"])[0], 1)
        self.assertIn("Delivery does not match", html.read_text(encoding="utf-8"))
        (self.root / "renamed.txt").write_bytes(b"changed")
        self.assertEqual(self.invoke(command + ["--force"])[0], 1)

    def test_cli_refuses_output_inside_scanned_folder(self):
        code, text = self.invoke(["scan", str(self.root), "--out", str(self.root / "receipt.json")])
        self.assertEqual(code, 2)
        self.assertIn("outside", text)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_cli_refuses_overwrite_and_input_output_alias(self):
        path = self.base / "receipt.json"
        self.assertEqual(self.invoke(["scan", str(self.root), "--out", str(path)])[0], 0)
        self.assertEqual(self.invoke(["scan", str(self.root), "--out", str(path)])[0], 2)
        self.assertEqual(self.invoke(["compare", str(path), str(path), "--html", str(path), "--force"])[0], 2)

    def test_cli_refuses_aliased_outputs_before_writing(self):
        path = self.base / "receipt.json"
        path.write_text(json.dumps(manifest([])), encoding="utf-8")
        output = self.base / "result.html"
        code, _ = self.invoke(["compare", str(path), str(path), "--html", str(output), "--json", str(output)])
        self.assertEqual(code, 2)
        self.assertFalse(output.exists())

    def test_cli_errors_do_not_create_success_report(self):
        path = self.base / "bad.json"
        path.write_text("[]", encoding="utf-8")
        output = self.base / "report.html"
        code, _ = self.invoke(["compare", str(path), str(path), "--html", str(output)])
        self.assertEqual(code, 2)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()

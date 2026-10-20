"""Behavioral tests use generated images, never user source files."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, PngImagePlugin

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "humanize.py"
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("humanize", SCRIPT)
humanize = importlib.util.module_from_spec(spec)
spec.loader.exec_module(humanize)


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ProcessingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def image(self, name="input.png", mode="RGB", size=(24, 16)):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        color = (110, 145, 175, 81) if mode == "RGBA" else (110, 145, 175)
        image = Image.new(mode, size, color)
        image.save(path)
        return path

    def run_cli(self, *arguments):
        env = dict(os.environ, PYTHONUTF8="1")
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, arguments)],
                              capture_output=True, text=True, encoding="utf-8", env=env)

    def test_unicode_nested_output_source_unchanged_and_report(self):
        source = self.image("\u56fe\u7247/\u793a\u4f8b.png")
        before = fingerprint(source)
        output = self.root / "\u8f93\u51fa" / "nested" / "result.jpg"
        report = self.root / "report.json"
        result = self.run_cli(source, "-o", output, "--seed", 12, "--report", report)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(fingerprint(source), before)
        with Image.open(output) as image:
            self.assertEqual(image.size, (24, 16))
        data = json.loads(report.read_text())
        self.assertEqual(data["success"], 1)
        self.assertEqual(data["results"][0]["input_sha256"], before)
        self.assertEqual(data["results"][0]["output_sha256"], fingerprint(output))
        self.assertEqual(list(output.parent.glob(".humanize-*")), [])

    def test_transparency_is_preserved(self):
        source = self.image(mode="RGBA")
        result = self.run_cli(source, "--seed", 42)
        self.assertEqual(result.returncode, 0, result.stderr)
        with Image.open(self.root / "input_humanized.png") as output:
            self.assertEqual(output.mode, "RGBA")
            self.assertEqual(output.getchannel("A").getextrema(), (81, 81))

    def test_metadata_only_png_retains_pixels_removes_text(self):
        source = self.root / "private.png"
        info = PngImagePlugin.PngInfo()
        info.add_text("Author", "private-author")
        original = Image.new("RGB", (10, 12), (30, 50, 70))
        original.save(source, pnginfo=info)
        output = self.root / "clean.png"
        result = self.run_cli(source, "-o", output, "--no-metadata")
        self.assertEqual(result.returncode, 0, result.stderr)
        with Image.open(output) as clean:
            self.assertNotIn("Author", clean.info)
            self.assertEqual(clean.tobytes(), original.tobytes())
        with Image.open(source) as untouched:
            self.assertEqual(untouched.info["Author"], "private-author")

    def test_exif_orientation_and_metadata(self):
        source = self.root / "rotated.jpg"
        exif = Image.Exif()
        exif[274] = 6
        exif[315] = "private-author"
        Image.new("RGB", (20, 10), "red").save(source, exif=exif)
        before = fingerprint(source)
        output = self.root / "rotated_clean.jpg"
        result = self.run_cli(source, "-o", output, "--metadata-only")
        self.assertEqual(result.returncode, 0, result.stderr)
        with Image.open(output) as clean:
            self.assertEqual(clean.size, (10, 20))
            self.assertEqual(len(clean.getexif()), 0)
        self.assertEqual(fingerprint(source), before)

    def test_seed_reproducibility_and_tiny_images(self):
        source = self.image(size=(1, 1))
        a, b = self.root / "a.jpg", self.root / "b.jpg"
        for output in [a, b]:
            result = self.run_cli(source, "-o", output, "--seed", 100, "--strength", "heavy")
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(a.read_bytes(), b.read_bytes())

    def test_never_overwrite_input_or_hardlink(self):
        source = self.image()
        before = fingerprint(source)
        linked = self.root / "linked.png"
        os.link(source, linked)
        for target in [source, linked]:
            result = self.run_cli(source, "-o", target, "--overwrite")
            self.assertEqual(result.returncode, 1)
        self.assertEqual(fingerprint(source), before)

    def test_existing_output_is_preserved(self):
        source = self.image()
        output = self.root / "existing.jpg"
        output.write_bytes(b"existing")
        result = self.run_cli(source, "-o", output)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(output.read_bytes(), b"existing")
        result = self.run_cli(source, "-o", output, "--overwrite")
        self.assertEqual(result.returncode, 0, result.stderr)
        with Image.open(output) as image:
            image.verify()

    def test_batch_collision_failure_and_exclusion(self):
        folder = self.root / "inputs"
        a = self.image("inputs/same.PNG")
        b = self.image("inputs/same.jpg")
        c = self.image("inputs/nested/deep.png")
        (folder / "broken.png").write_bytes(b"broken image")
        report = self.root / "batch.json"
        out = folder / "humanized_output"
        result = self.run_cli(folder, "--batch", "--recursive", "--report", report)
        self.assertEqual(result.returncode, 1)
        data = json.loads(report.read_text())
        self.assertEqual((data["success"], data["failed"]), (3, 1))
        self.assertTrue((out / "same.PNG_humanized.jpg").exists())
        self.assertTrue((out / "same.jpg_humanized.jpg").exists())
        self.assertTrue((out / "nested" / "deep.png_humanized.jpg").exists())
        result = self.run_cli(folder, "--batch", "--recursive", "--overwrite",
                              "--report", report)
        data = json.loads(report.read_text())
        self.assertEqual(len(data["results"]), 4)
        self.assertTrue(all(path.exists() for path in [a, b, c]))

    def test_report_cannot_replace_original(self):
        source = self.image()
        before = fingerprint(source)
        result = self.run_cli(source, "--report", source, "--overwrite")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(fingerprint(source), before)
        self.assertFalse((self.root / "input_humanized.jpg").exists())

    def test_reject_animation_and_parameter_conflict(self):
        animated = self.root / "animated.webp"
        Image.new("RGB", (4, 4), "red").save(
            animated, save_all=True, append_images=[Image.new("RGB", (4, 4), "blue")]
        )
        result = self.run_cli(animated)
        self.assertEqual(result.returncode, 1)
        source = self.image()
        result = self.run_cli(source, "-o", self.root / "bad.png", "--format", "jpg")
        self.assertEqual(result.returncode, 1)
        result = self.run_cli(source, "--seed", -1)
        self.assertEqual(result.returncode, 2)

    def test_missing_dependencies_are_actionable(self):
        result = subprocess.run(
            [sys.executable, "-S", str(ROOT / "scripts" / "check_deps.py")],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 3)
        data = json.loads(result.stdout)
        self.assertFalse(data["ready"])
        self.assertIn("pip", data["install_command"])

    def test_no_hardlink_filesystem_fallback(self):
        target = self.root / "result.png"
        with patch.object(humanize.os, "link", side_effect=OSError("unsupported")):
            humanize.publish(b"complete content", target, False)
        self.assertEqual(target.read_bytes(), b"complete content")
        with patch.object(humanize.os, "link", side_effect=OSError("unsupported")):
            with self.assertRaises(FileExistsError):
                humanize.publish(b"replacement", target, False)
        self.assertEqual(target.read_bytes(), b"complete content")

    def test_failed_copy_removes_partial_and_temp_files(self):
        target = self.root / "result.png"
        with patch.object(humanize.os, "link", side_effect=OSError("unsupported")):
            with patch.object(humanize.shutil, "copyfileobj", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    humanize.publish(b"image", target, False)
        self.assertFalse(target.exists())
        self.assertEqual(list(self.root.glob(".humanize-*")), [])


if __name__ == "__main__":
    unittest.main()

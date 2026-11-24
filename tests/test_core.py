import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from nexa_ai.file_store import guess_mime_type
from nexa_ai.local_backend import _parse_content, prepare_messages
from nexa_ai.model_library import MODEL_CATALOG
from nexa_ai.plugin_manager import PluginManager
from nexa_ai.file_store import StoredFile


class CoreTests(unittest.TestCase):
    def test_guess_mime_type_for_mp4(self):
        self.assertEqual(guess_mime_type("clip.mp4"), "video/mp4")

    def test_supplied_mime_type_wins(self):
        self.assertEqual(guess_mime_type("photo.bin", "image/jpeg"), "image/jpeg")

    def test_octet_stream_falls_back_to_extension(self):
        self.assertEqual(guess_mime_type("notes.pdf", "application/octet-stream"), "application/pdf")

    def test_parse_openai_text_content(self):
        self.assertEqual(_parse_content("hello"), "hello")
        self.assertEqual(_parse_content([{"type": "text", "text": "one"}, {"text": " two"}]), "one two")

    def test_prepare_plain_chat_messages(self):
        messages = [{"role": "user", "content": "hello"}]
        self.assertEqual(prepare_messages(messages), messages)

    def test_model_catalog_contains_multiple_roles(self):
        roles = {item["role"] for item in MODEL_CATALOG.values()}
        self.assertTrue({"Chat", "Coding", "Vision"}.issubset(roles))
        self.assertIn("mmproj_filename", MODEL_CATALOG["qwen2.5-vl-3b"])

    def test_image_attachment_requires_vision_model(self):
        with tempfile.TemporaryDirectory() as folder:
            image_path = Path(folder) / "sample.png"
            image_path.write_bytes(b"image-bytes")
            stored = StoredFile("image-1", "sample.png", str(image_path), "image/png", image_path.stat().st_size)
            with patch.dict(os.environ, {"NEXA_MM_PROJ_PATH": ""}), patch("nexa_ai.local_backend.file_store.get", return_value=stored):
                with self.assertRaisesRegex(RuntimeError, "Qwen2.5-VL"):
                    prepare_messages([{"role": "user", "content": [{"type": "input_file", "file_id": "image-1"}]}])

    def test_image_attachment_becomes_local_data_uri_with_vision(self):
        with tempfile.TemporaryDirectory() as folder:
            image_path = Path(folder) / "sample.png"
            image_path.write_bytes(b"fake-image-content")
            mmproj = Path(folder) / "mmproj.gguf"
            mmproj.write_bytes(b"local-projector")
            stored = StoredFile("image-2", "sample.png", str(image_path), "image/png", image_path.stat().st_size)
            with patch.dict(os.environ, {"NEXA_MM_PROJ_PATH": str(mmproj)}), patch("nexa_ai.local_backend.file_store.get", return_value=stored):
                result = prepare_messages([{"role": "user", "content": [{"type": "text", "text": "Describe it"}, {"type": "input_file", "file_id": "image-2"}]}])
            image_parts = [part for part in result[0]["content"] if part.get("type") == "image_url"]
            self.assertEqual(len(image_parts), 1)
            self.assertTrue(image_parts[0]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_plugin_toggle_persists(self):
        with tempfile.TemporaryDirectory() as folder:
            manager = PluginManager(Path(folder))
            manager.set_enabled("community-example", True)
            manager2 = PluginManager(Path(folder))
            self.assertTrue(manager2.enabled("community-example"))

    def test_imported_plugin_is_disabled_until_enabled(self):
        with tempfile.TemporaryDirectory() as folder:
            manager = PluginManager(Path(folder))
            plugin_zip = Path(folder) / "example.zip"
            with zipfile.ZipFile(plugin_zip, "w") as archive:
                archive.writestr("example-plugin/plugin.json", json.dumps({
                    "id": "example-plugin",
                    "name": "Example Plugin",
                    "entrypoint": "plugin.py",
                }))
                archive.writestr("example-plugin/helper.py", "MESSAGE = 'ok'\n")
                archive.writestr(
                    "example-plugin/plugin.py",
                    "from .helper import MESSAGE\ndef register(context):\n    context.add_command('example.run', lambda: MESSAGE)\n",
                )
            plugin_id = manager.import_plugin_zip(plugin_zip)
            self.assertEqual(plugin_id, "example-plugin")
            self.assertFalse(manager.enabled(plugin_id))
            manager.set_enabled(plugin_id, True)
            context = manager.load_enabled_imported_plugins()
            self.assertEqual(context.commands["example.run"](), "ok")

    def test_plugin_zip_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            manager = PluginManager(Path(folder))
            plugin_zip = Path(folder) / "unsafe.zip"
            with zipfile.ZipFile(plugin_zip, "w") as archive:
                archive.writestr("../escape.txt", "bad")
                archive.writestr("plugin.json", json.dumps({"id": "unsafe-plugin"}))
            with self.assertRaises(ValueError):
                manager.import_plugin_zip(plugin_zip)


if __name__ == "__main__":
    unittest.main()

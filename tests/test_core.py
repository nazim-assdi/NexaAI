import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from nexa_ai.file_store import guess_mime_type
from nexa_ai.local_backend import _parse_content, prepare_messages
from nexa_ai.model_library import MODEL_CATALOG
from nexa_ai.plugin_manager import PluginManager


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
                archive.writestr(
                    "example-plugin/plugin.py",
                    "def register(context):\n    context.add_command('example.run', lambda: 'ok')\n",
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

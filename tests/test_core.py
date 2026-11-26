import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from nexa_ai.file_store import guess_mime_type
from nexa_ai.local_backend import _parse_content, prepare_messages, _options, parse_ollama_stream_chunk
from nexa_ai.ollama_runtime import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_MODEL_SIZE, OllamaNotInstalled, OllamaRuntime
from nexa_ai.plugin_manager import PluginManager
from nexa_ai.file_store import StoredFile
from nexa_ai.history_store import HistoryStore
from nexa_ai.n8n_studio import build_n8n_messages, extract_n8n_json, workflow_json_text
from nexa_ai.server_config import build_uvicorn_config
from nexa_ai.api import ChatRequest
from nexa_ai.ui_layout import calculate_window_geometry
from nexa_ai.chat_layout import CHAT_SUGGESTIONS, recent_chat_label
from nexa_ai.chat_layout import build_chat_context, response_token_limit, enqueue_followup, take_followup, provider_is_ready
from nexa_ai.voice_utils import resample_mono_int16


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

    def test_ollama_runtime_uses_qwen25_coder_3b(self):
        self.assertEqual(OLLAMA_MODEL, "qwen2.5-coder:3b")
        self.assertIn("1.9 GB", OLLAMA_MODEL_SIZE)

    def test_ollama_runtime_explains_missing_installation(self):
        runtime = OllamaRuntime()
        with patch.object(runtime, "server_ready", return_value=False):
            with patch.object(OllamaRuntime, "find_executable", return_value=None):
                with self.assertRaisesRegex(OllamaNotInstalled, "bundled Ollama runtime is missing"):
                    runtime.ensure_server()

    def test_ollama_runtime_uses_nexa_private_port_and_model_store(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime = OllamaRuntime(models_dir=Path(folder) / "engine-models")
            self.assertEqual(runtime.base_url, OLLAMA_BASE_URL)
            self.assertEqual(OLLAMA_BASE_URL, "http://127.0.0.1:11439")
            self.assertEqual(runtime.models_dir, Path(folder) / "engine-models")

    def test_chat_api_request_has_no_cloud_provider_field(self):
        request = ChatRequest(messages=[{"role": "user", "content": "hello"}])
        self.assertFalse(hasattr(request, "provider"))

    def test_ollama_runtime_does_not_pull_an_already_installed_model(self):
        runtime = OllamaRuntime()
        with patch.object(runtime, "installed_models", return_value=["qwen2.5-coder:3b"]):
            runtime.ensure_model()
        self.assertFalse(runtime.started_by_nexa)

    def test_ollama_options_are_cpu_friendly(self):
        options = _options(0.2, 384)
        self.assertEqual(options["num_predict"], 384)
        self.assertEqual(options["num_ctx"], 4096)
        self.assertGreaterEqual(options["num_thread"], 1)
        self.assertLessEqual(options["num_thread"], 4)

    def test_ollama_stream_parser_returns_visible_text_and_done(self):
        self.assertEqual(parse_ollama_stream_chunk('{"message":{"content":"hello"},"done":false}'), ("hello", False))
        self.assertEqual(parse_ollama_stream_chunk('{"message":{"content":""},"done":true}'), ("", True))
        self.assertEqual(parse_ollama_stream_chunk("partial"), ("", False))

    def test_ollama_stream_parser_surfaces_server_errors(self):
        with self.assertRaisesRegex(RuntimeError, "model not found"):
            parse_ollama_stream_chunk('{"error":"model not found"}')

    def test_followup_queue_preserves_order_and_enforces_limit(self):
        queue = []
        self.assertTrue(enqueue_followup(queue, " second "))
        self.assertTrue(enqueue_followup(queue, "third", limit=2))
        self.assertFalse(enqueue_followup(queue, "fourth", limit=2))
        self.assertEqual(take_followup(queue), "second")
        self.assertEqual(take_followup(queue), "third")
        self.assertIsNone(take_followup(queue))

    def test_followup_queue_rejects_blank_messages(self):
        queue = []
        self.assertFalse(enqueue_followup(queue, "   "))
        self.assertEqual(queue, [])
    def test_uvicorn_config_disables_packaged_default_logging_formatter(self):
        config = build_uvicorn_config(object(), host="127.0.0.1", port=8000)
        self.assertIsNone(config.log_config)
        self.assertFalse(config.access_log)
        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.port, 8000)

    def test_ui_layout_keeps_chat_composer_inside_768p_screen(self):
        geometry = calculate_window_geometry(1366, 768)
        self.assertEqual(geometry, "1120x628+123+70")

    def test_ui_layout_adapts_to_small_laptop_display(self):
        geometry = calculate_window_geometry(1024, 680)
        self.assertEqual(geometry, "944x560+40+60")

    def test_chat_suggestions_cover_coding_and_automation(self):
        self.assertEqual(len(CHAT_SUGGESTIONS), 4)
        prompts = " ".join(item[2] for item in CHAT_SUGGESTIONS).lower()
        self.assertIn("debug", prompts)
        self.assertIn("n8n", prompts)
        self.assertIn("python", prompts)

    def test_recent_chat_label_is_compact_and_nonempty(self):
        self.assertEqual(recent_chat_label("A short chat"), "A short chat")
        self.assertEqual(len(recent_chat_label("A" * 80)), 30)
        self.assertEqual(recent_chat_label("   "), "New conversation")

    def test_response_profiles_offer_speed_and_detail_choices(self):
        self.assertEqual(response_token_limit("Quick"), 384)
        self.assertEqual(response_token_limit("Balanced"), 768)
        self.assertEqual(response_token_limit("Detailed"), 1280)
        self.assertEqual(response_token_limit("unknown"), 768)

    def test_chat_context_keeps_system_and_recent_turns_only(self):
        messages = [{"role": "system", "content": "rules"}]
        messages.extend({"role": "user" if i % 2 == 0 else "assistant", "content": str(i)} for i in range(14))
        context = build_chat_context(messages, max_recent_messages=8)
        self.assertEqual(context[0]["role"], "system")
        self.assertEqual(len(context), 9)
        self.assertEqual(context[-1]["content"], "13")
        self.assertEqual(context[1]["content"], "6")

    def test_voice_audio_resampler_converts_native_mic_rate_to_16khz(self):
        import numpy as np
        result = resample_mono_int16(np.arange(48000, dtype=np.int16), 48000, 16000)
        self.assertEqual(result.dtype, np.int16)
        self.assertEqual(len(result), 16000)

    def test_voice_audio_resampler_keeps_native_16khz_samples(self):
        import numpy as np
        source = np.array([0, 100, -100, 500], dtype=np.int16)
        result = resample_mono_int16(source, 16000, 16000)
        self.assertTrue(np.array_equal(result, source))

    def test_voice_audio_resampler_rejects_invalid_source_rate(self):
        import numpy as np
        with self.assertRaises(ValueError):
            resample_mono_int16(np.array([1, 2], dtype=np.int16), 0, 16000)
    def test_image_attachment_requires_vision_model(self):
        with tempfile.TemporaryDirectory() as folder:
            image_path = Path(folder) / "sample.png"
            image_path.write_bytes(b"image-bytes")
            stored = StoredFile("image-1", "sample.png", str(image_path), "image/png", image_path.stat().st_size)
            with patch("nexa_ai.local_backend.file_store.get", return_value=stored):
                with self.assertRaisesRegex(RuntimeError, "Qwen2.5-Coder"):
                    prepare_messages([{"role": "user", "content": [{"type": "input_file", "file_id": "image-1"}]}])

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

    def test_history_store_saves_lists_loads_and_deletes(self):
        with tempfile.TemporaryDirectory() as folder:
            store = HistoryStore(Path(folder))
            conversation_id = "a" * 32
            messages = [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "Build an n8n workflow"},
                {"role": "assistant", "content": "Here is the plan."},
            ]
            store.save(conversation_id, "n8n workflow", messages, "qwen2.5-coder:3b")
            items = store.list_conversations()
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["title"], "n8n workflow")
            loaded = store.load(conversation_id)
            self.assertEqual(loaded["messages"], messages)
            self.assertTrue(store.delete(conversation_id))
            self.assertEqual(store.list_conversations(), [])

    def test_history_store_rejects_path_traversal_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            store = HistoryStore(Path(folder))
            with self.assertRaises(ValueError):
                store.load("../secrets")

    def test_n8n_prompt_is_local_and_requires_description(self):
        with self.assertRaises(ValueError):
            build_n8n_messages("   ")
        messages = build_n8n_messages("Create a local file watcher")
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("n8n workflow", messages[0]["content"].lower())

    def test_n8n_json_extraction_from_markdown(self):
        raw = """Here is your workflow:
\x60\x60\x60json
{"name":"Local demo","nodes":[{"id":"1","name":"Manual","type":"n8n-nodes-base.manualTrigger","typeVersion":1,"position":[240,300],"parameters":{}}],"connections":{},"settings":{"executionOrder":"v1"}}
\x60\x60\x60
"""
        workflow = extract_n8n_json(raw)
        self.assertEqual(workflow["name"], "Local demo")
        self.assertIn('"nodes"', workflow_json_text(workflow))

    def test_n8n_validator_rejects_dangling_connection(self):
        raw = {
            "name": "Broken",
            "nodes": [{"name": "Manual", "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "position": [0, 0], "parameters": {}}],
            "connections": {"Manual": {"main": [[{"node": "Missing", "type": "main", "index": 0}]]}},
        }
        with self.assertRaisesRegex(ValueError, "unknown node"):
            extract_n8n_json(json.dumps(raw))

    def test_plugin_zip_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            manager = PluginManager(Path(folder))
            plugin_zip = Path(folder) / "unsafe.zip"
            with zipfile.ZipFile(plugin_zip, "w") as archive:
                archive.writestr("../escape.txt", "bad")
                archive.writestr("plugin.json", json.dumps({"id": "unsafe-plugin"}))
            with self.assertRaises(ValueError):
                manager.import_plugin_zip(plugin_zip)


    def test_gemini_readiness_does_not_depend_on_local_qwen(self):
        self.assertTrue(provider_is_ready("gemini", local_ready=False, gemini_key_available=True))
        self.assertFalse(provider_is_ready("gemini", local_ready=True, gemini_key_available=False))

    def test_offline_readiness_still_requires_local_engine(self):
        self.assertTrue(provider_is_ready("local", local_ready=True, gemini_key_available=False))
        self.assertFalse(provider_is_ready("local", local_ready=False, gemini_key_available=True))


if __name__ == "__main__":
    unittest.main()

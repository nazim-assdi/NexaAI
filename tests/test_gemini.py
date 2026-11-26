import os
import unittest

from nexa_ai.gemini_backend import GEMINI_MODELS, build_request, test_api_key
from nexa_ai.secure_store import DPAPISecretStore


class GeminiBackendTests(unittest.TestCase):
    def test_only_current_gemini_flash_models_are_selectable(self):
        self.assertEqual(
            set(GEMINI_MODELS),
            {"gemini-3.8-flash", "gemini-3.1-flash-lite"},
        )

    def test_gemini_request_translates_chat_roles_and_system_instruction(self):
        request = build_request([
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "Write a Python function."},
            {"role": "assistant", "content": "Sure."},
            {"role": "user", "content": "Add type hints."},
        ], temperature=0.3, max_tokens=512)
        self.assertEqual(request["systemInstruction"]["parts"][0]["text"], "Be concise.")
        self.assertEqual([item["role"] for item in request["contents"]], ["user", "model", "user"])
        self.assertEqual(request["generationConfig"]["maxOutputTokens"], 512)
        self.assertEqual(request["generationConfig"]["temperature"], 0.3)

    def test_gemini_request_rejects_empty_chat(self):
        with self.assertRaisesRegex(ValueError, "Add a message"):
            build_request([])

    def test_gemini_key_validation_rejects_empty_key(self):
        with self.assertRaisesRegex(ValueError, "API key"):
            test_api_key("")

    def test_gemini_key_validation_rejects_unknown_model(self):
        with self.assertRaisesRegex(ValueError, "Unsupported Gemini model"):
            test_api_key("not-a-real-key", "unknown-model")

    def test_dpapi_secret_path_is_scoped_and_rejects_traversal(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as folder:
            store = DPAPISecretStore(folder)
            self.assertEqual(store._path("gemini_api_key").name, "gemini_api_key.dpapi")
            with self.assertRaises(ValueError):
                store._path("../secret")

    @unittest.skipIf(os.name == "nt", "Windows test runner exercises native DPAPI.")
    def test_dpapi_does_not_fall_back_to_plaintext_on_non_windows(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as folder:
            store = DPAPISecretStore(folder)
            with self.assertRaisesRegex(RuntimeError, "only supported on Windows"):
                store.set_secret("gemini_api_key", "example-key")


if __name__ == "__main__":
    unittest.main()

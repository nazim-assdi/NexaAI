import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nexa_ai import cloud_runtime
from nexa_ai.api import ChatRequest
from nexa_ai.secure_store import _target


class CloudRuntimeTests(unittest.TestCase):
    def test_credential_targets_are_namespaced_and_validated(self):
        self.assertEqual(_target("gemini"), "NexaAI/FreeLM/gemini")
        with self.assertRaises(ValueError):
            _target("../../unexpected")

    def test_chat_request_defaults_to_offline_provider(self):
        request = ChatRequest(messages=[{"role": "user", "content": "hello"}])
        self.assertEqual(request.provider, "local")

    def test_chat_request_accepts_freelm_provider(self):
        request = ChatRequest(messages=[{"role": "user", "content": "hello"}], provider="freelm")
        self.assertEqual(request.provider, "freelm")

    def test_provider_status_lists_only_saved_provider_names(self):
        with patch("nexa_ai.cloud_runtime.has_secret", side_effect=lambda name: name == "gemini"):
            with patch("nexa_ai.cloud_runtime.load_settings", return_value={"allow_public_endpoints": False}):
                status = cloud_runtime.provider_status()
        self.assertTrue(status["configured"])
        self.assertEqual(status["providers"], ["Google Gemini"])
        self.assertEqual(status["saved_fields"], ["gemini"])

    def test_public_endpoint_permission_is_off_by_default(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "cloud-settings.json"
            with patch("nexa_ai.cloud_runtime._SETTINGS_PATH", target):
                with patch("nexa_ai.cloud_runtime._APP_DIR", Path(folder)):
                    self.assertFalse(cloud_runtime.load_settings()["allow_public_endpoints"])
                    cloud_runtime.save_settings(allow_public_endpoints=True)
                    self.assertTrue(cloud_runtime.load_settings()["allow_public_endpoints"])

    def test_build_client_restores_environment_after_loading_secure_keys(self):
        existing = os.environ.get("GEMINI_API_KEY")
        with patch("nexa_ai.cloud_runtime.get_secret", side_effect=lambda slot: "test-secret" if slot == "gemini" else ""):
            with patch("nexa_ai.cloud_runtime.load_settings", return_value={"allow_public_endpoints": False}):
                with patch("freelm.FreeLLM.from_env", return_value=object()) as from_env:
                    result = cloud_runtime._build_client()
        self.assertIsNotNone(result)
        self.assertFalse(from_env.call_args.kwargs["keyless"])
        self.assertEqual(from_env.call_args.kwargs["strategy"], "quota_aware")
        self.assertEqual(os.environ.get("GEMINI_API_KEY"), existing)


if __name__ == "__main__":
    unittest.main()

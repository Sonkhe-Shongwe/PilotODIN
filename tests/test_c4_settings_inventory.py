"""Inert fixtures for the C4 candidate inventory; no application imports."""
import unittest

from tools.c4_settings_inventory import classify


class SettingsInventoryTests(unittest.TestCase):
    def test_paths_schema_and_legacy_stage(self):
        found = classify(
            "target = HOME / 'ai_settings.json'\n"
            "tmp = HOME / 'ai_settings.tmp'\n"
            "value = {'cloud_enabled': False}\n"
            "path = '.resource-policy-'\n"
            "secret = HOME / 'ai_secrets.dpapi'\n"
        )
        self.assertEqual(found["settings-file"], [1, 2, 5])
        self.assertEqual(found["settings-schema"], [3])
        self.assertEqual(found["settings-stage"], [4])

    def test_service_alias_and_direct_import_candidates(self):
        found = classify(
            "from backend import ai_provider as ai\n"
            "from backend.ai_provider import _read_config as read\n"
            "patch.object(ai, 'CONFIG_PATH', fixture)\n"
            "from backend import resource_policy as policy\n"
            "from backend.resource_policy import save_policy as save\n"
        )
        self.assertEqual(found["settings-service"], [1, 2, 4, 5])
        self.assertEqual(found["settings-symbol"], [2, 3, 5])

    def test_http_and_provider_candidates_without_returning_values(self):
        found = classify(
            "client.put('/api/ai/key', json={'key':'inert-marker'})\n"
            "put('/resource/policy', value)\n"
            "client.get('/api/ai/settings')\n"
            "os.environ['GEMINI_API_KEY'] = 'inert-marker'\n"
        )
        self.assertEqual(found["settings-http"], [1, 2, 3])
        self.assertEqual(found["key-provider"], [4])
        self.assertNotIn("inert-marker", repr(found))

    def test_ownership_and_build_candidates(self):
        found = classify(
            "hold_process_workspace(home)\n"
            "storage.check_write_path(path)\n"
            "stage_workspace_backup(source, destination)\n"
            "python -m PyInstaller --add-data example\n"
        )
        self.assertEqual(found["workspace-ownership"], [1, 2])
        self.assertEqual(found["backup-build"], [3, 4])

    def test_no_execution_or_unrelated_match(self):
        self.assertEqual(classify("raise RuntimeError('never execute')\n"), {})


if __name__ == "__main__":
    unittest.main()

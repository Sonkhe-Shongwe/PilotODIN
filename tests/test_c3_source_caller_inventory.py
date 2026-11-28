"""Pure static scanner fixtures. Never import the application or open a socket."""
import unittest

from tools.c3_source_caller_inventory import classify


class IndirectCallerInventoryTests(unittest.TestCase):
    def scan(self, source, path="fixture.py"):
        found, failed = classify(path, source, {"health", "projects"})
        self.assertFalse(failed)
        return found

    def test_opener_alias_bound_method_and_proxy_reference(self):
        found = self.scan(
            "from urllib.request import build_opener as make\n"
            "client = make()\n"
            "send = client.open\n"
            "send('synthetic')\n"
        )
        self.assertEqual(found["python-http-call"], {2, 4})
        self.assertEqual(found["indirect-http"], {1})

    def test_http_connection_alias(self):
        found = self.scan(
            "import http.client as hc\n"
            "connection = hc.HTTPConnection('synthetic')\n"
            "connection.request('GET', '/')\n"
            "connection.getresponse()\n"
        )
        self.assertEqual(found["python-http-call"], {2, 3, 4})

    def test_httpx_session_and_launcher_aliases(self):
        found = self.scan(
            "from httpx import AsyncClient as Client\n"
            "import subprocess as sp\n"
            "client = Client()\n"
            "client.get('/api/health')\n"
            "launch = sp.Popen\n"
            "launch(['synthetic'])\n"
        )
        self.assertEqual(found["python-http-call"], {3, 4})
        self.assertEqual(found["python-launch-call"], {6})

    def test_module_app_and_endpoint_aliases(self):
        found = self.scan(
            "import backend as b\n"
            "m = b.main\n"
            "application = m.app\n"
            "read = m.health\n"
            "read()\n"
            "serve(application)\n"
        )
        self.assertEqual(found["python-main-app-reference"], {3, 6})
        self.assertEqual(found["python-route-alias-reference"], {4, 5})
        self.assertEqual(found["python-route-alias-call"], {5})

    def test_imported_app_and_endpoint_alias(self):
        found = self.scan(
            "from backend.main import app as api, projects as listing\n"
            "serve(api)\n"
            "listing()\n"
        )
        self.assertEqual(found["python-main-app-reference"], {2})
        self.assertEqual(found["python-route-alias-call"], {3})
        self.assertEqual(found["direct-route-import"], {1})

    def test_dynamic_main_import_and_getattr(self):
        found = self.scan(
            "from importlib import import_module as load\n"
            "mod = load('backend.main')\n"
            "serve(mod.app)\n"
            "getattr(mod, 'health')\n"
        )
        self.assertEqual(found["python-dynamic-import-call"], {2})
        self.assertEqual(found["python-main-app-reference"], {3})
        self.assertEqual(found["python-dynamic-main-reference"], {4})

    def test_nonpython_launcher_and_credential_indicators(self):
        found = self.scan(
            "Start-Process python\n"
            "$env:PILOTODIN_CONTROL_CAPABILITY = 'synthetic'\n"
            "Invoke-RestMethod -Headers @{}\n",
            "fixture.ps1",
        )
        self.assertEqual(found["process-launch"], {1})
        self.assertEqual(found["credential-boundary"], {2})
        self.assertEqual(found["indirect-http"], {3})

    def test_unrelated_file_open_not_http_call(self):
        found = self.scan("with open('synthetic') as file:\n    file.read()\n")
        self.assertNotIn("python-http-call", found)

    def test_source_is_not_executed(self):
        found = self.scan("raise RuntimeError('never execute')\nimport urllib.request\n")
        self.assertNotIn("python-http-call", found)


if __name__ == "__main__":
    unittest.main()

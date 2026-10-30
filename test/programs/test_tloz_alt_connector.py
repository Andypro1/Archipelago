"""Set MESEN_EXE and TLOZ_TEST_ROM to run the connector in Mesen's Lua 5.4 runtime."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.environ.get("MESEN_EXE") and os.environ.get("TLOZ_TEST_ROM"),
                     "Requires MESEN_EXE and TLOZ_TEST_ROM")
class TestTlozAltConnector(unittest.TestCase):
    def test_emulator_backends(self):
        root = Path(__file__).resolve().parents[2]
        for backend in ("Mesen2", "NesHawk", "QuickNES"):
            with self.subTest(backend=backend), tempfile.TemporaryDirectory() as folder:
                folder = Path(folder)
                rom = folder / f"tloz-connector-{folder.name}-{backend}.nes"
                shutil.copyfile(os.environ["TLOZ_TEST_ROM"], rom)
                output = folder / "result.txt"
                script = folder / "test.lua"
                script.write_text(
                    f"TEST_ROOT = {json.dumps(root.as_posix())}\n"
                    f"TEST_OUTPUT = {json.dumps(output.as_posix())}\n"
                    f"TEST_BACKEND = {json.dumps(backend)}\n"
                    f"dofile({json.dumps((root / 'test/lua/test_tloz_alt.lua').as_posix())})\n",
                    encoding="utf-8",
                )
                result = subprocess.run(
                    [os.environ["MESEN_EXE"], "--testRunner", str(rom), str(script)],
                    cwd=folder, capture_output=True, text=True, timeout=30,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                message = output.read_text() if output.exists() else result.stdout + result.stderr
                self.assertEqual(result.returncode, 0, message)
                self.assertEqual(message, f"{backend}: passed")

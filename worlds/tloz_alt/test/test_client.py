import asyncio
import importlib
import json
from pathlib import Path
from pkgutil import get_data
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from .. import Client, connector_resources


def connector_reply(**changes):
    return {"protocol": Client.PROTOCOL_VERSION, "game": Client.TLoZWorld.game,
            "romName": "LZA069_1_test_seed", "playerName": list(b"Tester".ljust(32, b"\0")), **changes}


class TestClient(unittest.IsolatedAsyncioTestCase):
    async def test_handshake_precedes_inventory_over_tcp(self):
        ctx = Client.ZeldaContext(None, None)
        ctx.items_received = [SimpleNamespace(item=7123)]
        requests = []

        async def emulator(reader, writer):
            try:
                for _ in range(2):
                    requests.append(json.loads(await reader.readline()))
                    writer.write((json.dumps(connector_reply()) + "\n").encode())
                    await writer.drain()
                ctx.exit_event.set()
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_server(emulator, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        open_connection = asyncio.open_connection
        try:
            with patch.object(Client.asyncio, "open_connection", new=lambda *a, **k: open_connection("127.0.0.1", port)):
                await asyncio.wait_for(Client.nes_sync_task(ctx), timeout=5)
            self.assertNotIn("items", requests[0])
            self.assertEqual(requests[1]["items"], [7123])
            self.assertEqual(requests[1]["romName"], connector_reply()["romName"])
            self.assertEqual(ctx.auth, "Tester")
        finally:
            server.close()
            await server.wait_closed()
            await ctx.shutdown()

    async def test_rejects_stale_connector_and_changed_rom(self):
        ctx = Client.ZeldaContext(None, None)
        try:
            for data in ({}, [], connector_reply(protocol=99), connector_reply(game="The Legend of Zelda"),
                         connector_reply(romName="LOZ_native"), connector_reply(error="wrong ROM"),
                         connector_reply(playerName=[])):
                with self.subTest(data=data), self.assertRaises(ValueError):
                    Client.validate_connector(ctx, data)
                self.assertFalse(ctx.connector_ready)
            Client.validate_connector(ctx, connector_reply())
            with self.assertRaisesRegex(ValueError, "ROM changed"):
                Client.validate_connector(ctx, connector_reply(romName="LZA_other_seed"))
            ctx.auth = "AnotherPlayer"
            with self.assertRaisesRegex(ValueError, "player changed"):
                Client.validate_connector(ctx, connector_reply())
        finally:
            await ctx.shutdown()


class TestConnectorResources(unittest.TestCase):
    def test_export_from_zip_without_shared_lua_files(self):
        package = "tloz_connector_fixture"
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            archive_path = directory / "resources.apworld"
            with ZipFile(archive_path, "w") as archive:
                archive.writestr(f"{package}/__init__.py", "")
                archive.writestr(f"{package}/archipelago.json", '{"world_version": "1.1.0"}')
                for name in connector_resources.RESOURCE_FILES:
                    archive.writestr(f"{package}/data/lua/{name}", get_data("worlds.tloz_alt", f"data/lua/{name}"))
            sys.path.insert(0, str(archive_path))
            try:
                importlib.import_module(package)
                with patch.object(connector_resources, "__package__", package), \
                        patch.object(connector_resources, "user_path", side_effect=lambda *parts: str(directory.joinpath(*parts))):
                    script = connector_resources.export_connector()
                    self.assertTrue(script.is_file())
                    self.assertTrue(script.parent.name.startswith("1.1.0-"))
                    self.assertEqual(connector_resources.export_connector(), script)
                    for name in connector_resources.RESOURCE_FILES:
                        self.assertEqual((script.parent / name).read_bytes(), get_data(package, f"data/lua/{name}"))
            finally:
                sys.path.remove(str(archive_path))
                sys.modules.pop(package, None)

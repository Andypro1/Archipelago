import asyncio
import unittest
from argparse import Namespace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import Zelda1Client
from worlds.LauncherComponents import identify


class TestZeldaClient(unittest.IsolatedAsyncioTestCase):
    async def test_authentication_uses_selected_game(self):
        for alt, game in ((False, "The Legend of Zelda"), (True, "The Legend of Zelda (Alt)")):
            with self.subTest(game=game):
                ctx = Zelda1Client.ZeldaContext(None, None, alt=alt)
                ctx.auth = "test-rom"
                ctx.send_msgs = AsyncMock()
                try:
                    await ctx.server_auth(False)
                    packet = ctx.send_msgs.call_args_list[0].args[0][0]
                    self.assertEqual(packet["game"], game)
                    self.assertEqual(packet["name"], "test-rom")
                    self.assertEqual(ctx.item_names.lookup_in_game(7100), "Boomerang")
                    self.assertIn(game, ctx.checksums)
                finally:
                    await ctx.shutdown()

    async def test_patch_and_manual_variant_selection(self):
        for filename, flag, expected in (("", False, False), ("", True, True),
                                         ("test.aptloz", True, False), ("test.aptlozalt", False, True)):
            with self.subTest(filename=filename, flag=flag):
                settings = SimpleNamespace(display_msgs=False, rom_start=False)
                ctx = Mock(world_type=SimpleNamespace(settings=settings), exit_event=asyncio.Event(),
                           shutdown=AsyncMock())
                ctx.exit_event.set()
                args = Namespace(diff_file=filename, alt=flag, connect=None, password=None)
                with patch.object(Zelda1Client, "ZeldaContext", return_value=ctx) as context, \
                        patch.object(Zelda1Client, "server_loop", new_callable=AsyncMock), \
                        patch.object(Zelda1Client, "nes_sync_task", new_callable=AsyncMock), \
                        patch.object(Zelda1Client, "run_game", new_callable=AsyncMock) as run_game, \
                        patch.object(Zelda1Client, "gui_enabled", False), \
                        patch.object(Zelda1Client, "DISPLAY_MSGS", True), \
                        patch("Patch.create_rom_file", return_value=({"server": "localhost:38281"}, "test.nes")):
                    await Zelda1Client.main(args)
                    context.assert_called_once_with(None, None, alt=expected)
                    self.assertFalse(Zelda1Client.DISPLAY_MSGS)
                    if filename:
                        run_game.assert_awaited_once_with("test.nes", False)
                    else:
                        run_game.assert_not_called()

    async def test_launcher_routes_both_patch_types(self):
        self.assertEqual(identify("test.aptloz")[1].display_name, "Zelda 1 Client")
        alternate = identify("test.aptlozalt")[1]
        self.assertEqual(alternate.display_name, "Zelda 1 Client (Alt)")
        with patch("worlds.LauncherComponents.get_exe", return_value=["python", "Zelda1Client.py"]), \
                patch("worlds.LauncherComponents.launch_exe") as launch:
            alternate.run("test.aptlozalt")
            launch.assert_called_once_with(["python", "Zelda1Client.py", "--alt", "test.aptlozalt"])

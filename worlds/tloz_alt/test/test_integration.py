import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from Fill import distribute_items_restrictive
from Patch import create_rom_file
from test.general import setup_multiworld
from worlds.tloz import TLoZWorld as NativeWorld
from worlds.tloz.Rom import TLoZDeltaPatch as NativePatch
from .. import TLoZWorld
from ..Rom import TLoZDeltaPatch


class TestIntegration(unittest.TestCase):
    def test_mixed_world_generation(self):
        multiworld = setup_multiworld([NativeWorld, TLoZWorld], seed=12345)
        distribute_items_restrictive(multiworld)
        self.assertTrue(multiworld.can_beat_game())
        self.assertEqual(NativeWorld.location_name_to_id, TLoZWorld.location_name_to_id)
        for player in multiworld.player_ids:
            for location in multiworld.get_locations(player):
                self.assertEqual(location.game, multiworld.game[player])
                self.assertEqual(location.item.game, multiworld.game[location.item.player])

    def test_patch_round_trip(self):
        source = b"base ROM for patch routing test"
        with tempfile.TemporaryDirectory() as directory:
            for patch_type in (NativePatch, TLoZDeltaPatch):
                with self.subTest(game=patch_type.game):
                    target = source + patch_type.game.encode()
                    rom_path = Path(directory, "patched.nes")
                    rom_path.write_bytes(target)
                    patch_path = Path(directory, "player" + patch_type.patch_file_ending)
                    with patch.object(patch_type, "get_source_data_with_cache", return_value=source):
                        patch_type(str(patch_path), player=1, player_name="Tester", patched_path=str(rom_path)).write()
                        metadata, result = create_rom_file(str(patch_path))
                    self.assertEqual(Path(result).read_bytes(), target)
                    self.assertEqual(metadata["player_name"], "Tester")
                    with ZipFile(patch_path) as archive:
                        self.assertEqual(json.loads(archive.read("archipelago.json"))["game"], patch_type.game)

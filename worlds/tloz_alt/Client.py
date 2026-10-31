# Based (read: copied almost wholesale and edited) off the FF1 Client.

import asyncio
import copy
import json
import logging
import os
import subprocess
import time
import typing
from asyncio import StreamReader, StreamWriter

import Utils
from Utils import async_start
from CommonClient import CommonContext, server_loop, gui_enabled, ClientCommandProcessor, logger, \
    get_base_parser

from . import Locations, Rom, TLoZWorld
from .connector_resources import export_connector

PROTOCOL_VERSION = 1

SYSTEM_MESSAGE_ID = 0

CONNECTION_TENTATIVE_STATUS = "Initial Connection Made"
CONNECTION_CONNECTED_STATUS = "Connected"
CONNECTION_INITIAL_STATUS = "Connection has not been initiated"

DISPLAY_MSGS = True

class ZeldaCommandProcessor(ClientCommandProcessor):

    def _cmd_nes(self):
        """Check NES Connection State"""
        if isinstance(self.ctx, ZeldaContext):
            logger.info(f"NES Status: {self.ctx.nes_status}")

    def _cmd_toggle_msgs(self):
        """Toggle displaying messages in the emulator"""
        global DISPLAY_MSGS
        DISPLAY_MSGS = not DISPLAY_MSGS
        logger.info(f"Messages are now {'enabled' if DISPLAY_MSGS else 'disabled'}")


class ZeldaContext(CommonContext):
    command_processor = ZeldaCommandProcessor
    items_handling = 0b101  # get sent remote and starting items
    # Infinite Hyrule compatibility
    overworld_item = 0x5F
    armos_item = 0x24

    game = TLoZWorld.game

    def __init__(self, server_address, password):
        self.world_type = TLoZWorld
        self.connector_script = "connector_tloz_alt.lua"
        self.rom_name = None
        self.connector_ready = False
        super().__init__(server_address, password)
        self.bonus_items = []
        self.nes_streams: tuple[StreamReader, StreamWriter] | None = None
        self.nes_sync_task = None
        self.messages = {}
        self.locations_array = None
        self.nes_status = CONNECTION_INITIAL_STATUS
        self.awaiting_rom = False
        self.shop_slots_left = 0
        self.shop_slots_middle = 0
        self.shop_slots_right = 0
        self.shop_slots = [self.shop_slots_left, self.shop_slots_middle, self.shop_slots_right]
        self.slot_data = dict()

    async def server_auth(self, password_requested: bool = False):
        if password_requested and not self.password:
            await super(ZeldaContext, self).server_auth(password_requested)
        if not self.auth:
            self.awaiting_rom = True
            logger.info('Awaiting connection to NES to get Player information')
            return

        await self.send_connect()

    def _set_message(self, msg: str, msg_id: int):
        if DISPLAY_MSGS:
            self.messages[(time.time(), msg_id)] = msg

    def on_package(self, cmd: str, args: dict):
        if cmd == 'Connected':
            self.slot_data = args.get("slot_data", {})
            asyncio.create_task(parse_locations(self.locations_array, self, True))
        elif cmd == 'Print':
            msg = args['text']
            if ': !' not in msg:
                self._set_message(msg, SYSTEM_MESSAGE_ID)

    def on_print_json(self, args: dict):
        if self.ui:
            self.ui.print_json(copy.deepcopy(args["data"]))
        else:
            text = self.jsontotextparser(copy.deepcopy(args["data"]))
            logger.info(text)
        relevant = args.get("type", None) in {"Hint", "ItemSend"}
        if relevant:
            item = args["item"]
            # goes to this world
            if self.slot_concerns_self(args["receiving"]):
                relevant = True
            # found in this world
            elif self.slot_concerns_self(item.player):
                relevant = True
            # not related
            else:
                relevant = False
            if relevant:
                item = args["item"]
                msg = self.raw_text_parser(copy.deepcopy(args["data"]))
                self._set_message(msg, item.item)

    def run_gui(self):
        from kvui import GameManager

        class ZeldaManager(GameManager):
            logging_pairs = [
                ("Client", "Archipelago")
            ]
            base_title = "Archipelago Zelda 1 Client (Alt)"

        self.ui = ZeldaManager(self)
        self.ui_task = asyncio.create_task(self.ui.async_run(), name="UI")


def get_payload(ctx: ZeldaContext):
    # Until the connector confirms its ROM, send only a handshake, never inventory writes.
    payload = {"protocol": PROTOCOL_VERSION, "game": ctx.game}
    if ctx.connector_ready:
        payload.update({
            "romName": ctx.rom_name,
            "items": [item.item for item in ctx.items_received],
            "messages": {f'{key[0]}:{key[1]}': value for key, value in ctx.messages.items()
                         if key[0] > time.time() - 10},
            "shops": {"left": ctx.shop_slots_left, "middle": ctx.shop_slots_middle, "right": ctx.shop_slots_right},
            "bonusItems": list(ctx.bonus_items),
        })
    return json.dumps(payload)


def validate_connector(ctx: ZeldaContext, data: dict) -> str:
    """Reject stale scripts or a changed ROM before allowing the next inventory payload."""
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object from the Zelda (Alt) connector")
    if data.get("protocol") != PROTOCOL_VERSION or data.get("game") != ctx.game:
        raise ValueError(f"Incompatible connector. Load the exported script: {ctx.connector_script}")
    if data.get("error"):
        raise ValueError(data["error"])
    rom_name = data.get("romName", "")
    if not isinstance(rom_name, str) or not rom_name.startswith("LZA"):
        raise ValueError("Load a patched The Legend of Zelda (Alt) ROM.")
    if ctx.rom_name is not None and ctx.rom_name != rom_name:
        raise ValueError("The ROM changed. Restart this client before connecting to another seed or slot.")
    auth = bytes(data["playerName"]).rstrip(b"\0").decode("utf-8")
    if not auth:
        raise ValueError("The ROM has no player name. Apply your .aptlozalt patch again.")
    if ctx.auth and ctx.auth != auth:
        raise ValueError("The player changed. Restart this client before connecting to another slot.")
    ctx.rom_name = rom_name
    ctx.connector_ready = True
    return auth


def reconcile_shops(ctx: ZeldaContext):
    checked_location_names = [ctx.location_names.lookup_in_game(location) for location in ctx.checked_locations]
    shops = [location for location in checked_location_names if "Shop" in location]
    left_slots = [shop for shop in shops if "Left" in shop]
    middle_slots = [shop for shop in shops if "Middle" in shop]
    right_slots = [shop for shop in shops if "Right" in shop]
    for shop in left_slots:
        ctx.shop_slots_left |= get_shop_bit_from_name(shop)
    for shop in middle_slots:
        ctx.shop_slots_middle |= get_shop_bit_from_name(shop)
    for shop in right_slots:
        ctx.shop_slots_right |= get_shop_bit_from_name(shop)


def get_shop_bit_from_name(location_name):
    if "Potion" in location_name:
        return Rom.potion_shop
    elif "Arrow" in location_name:
        return Rom.arrow_shop
    elif "Shield" in location_name:
        return Rom.shield_shop
    elif "Ring" in location_name:
        return Rom.ring_shop
    elif "Candle" in location_name:
        return Rom.candle_shop
    elif "Take" in location_name:
        return Rom.take_any
    return 0  # this should never be hit


async def parse_locations(locations_array, ctx: ZeldaContext, force: bool, zone="None"):
    if locations_array == ctx.locations_array and not force:
        return
    else:
        # print("New values")
        ctx.locations_array = locations_array
        locations_checked = []
        location = None
        for location in ctx.missing_locations:
            location_name = ctx.location_names.lookup_in_game(location)

            if location_name in Locations.overworld_locations and zone == "overworld":
                status = locations_array[Locations.major_location_offsets[location_name]]
                if location_name == "Ocean Heart Container":
                    status = locations_array[ctx.overworld_item]
                if location_name == "Armos Knights":
                    status = locations_array[ctx.armos_item]
                if status & 0x10:
                    ctx.locations_checked.add(location)
                    locations_checked.append(location)
            elif location_name in Locations.underworld1_locations and zone == "underworld1":
                status = locations_array[Locations.floor_location_game_offsets_early[location_name]]
                if status & 0x10:
                    ctx.locations_checked.add(location)
                    locations_checked.append(location)
            elif location_name in Locations.underworld2_locations and zone == "underworld2":
                status = locations_array[Locations.floor_location_game_offsets_late[location_name]]
                if status & 0x10:
                    ctx.locations_checked.add(location)
                    locations_checked.append(location)
            elif (location_name in Locations.shop_locations or "Take" in location_name) and zone == "caves":
                shop_bit = get_shop_bit_from_name(location_name)
                slot = 0
                context_slot = 0
                if "Left" in location_name:
                    slot = "slot1"
                    context_slot = 0
                elif "Middle" in location_name:
                    slot = "slot2"
                    context_slot = 1
                elif "Right" in location_name:
                    slot = "slot3"
                    context_slot = 2
                if locations_array[slot] & shop_bit > 0:
                    locations_checked.append(location)
                    ctx.shop_slots[context_slot] |= shop_bit
                if locations_array["takeAnys"] and locations_array["takeAnys"] >= 4:
                    if "Take Any" in location_name:
                        short_name = None
                        if "Left" in location_name:
                            short_name = "TakeAnyLeft"
                        elif "Middle" in location_name:
                            short_name = "TakeAnyMiddle"
                        elif "Right" in location_name:
                            short_name = "TakeAnyRight"
                        if short_name is not None:
                            item_code = ctx.slot_data[short_name]
                            if item_code > 0:
                                ctx.bonus_items.append(item_code)
                            locations_checked.append(location)
        if locations_checked:
            await ctx.send_msgs([
                {"cmd": "LocationChecks",
                 "locations": locations_checked}
            ])


async def nes_sync_task(ctx: ZeldaContext):
    logger.info("Starting NES connector. Use /nes for status information")
    while not ctx.exit_event.is_set():
        try:
            if ctx.nes_streams is None:
                ctx.connector_ready = False
                ctx.nes_streams = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", 52980), timeout=10)
                ctx.nes_status = CONNECTION_TENTATIVE_STATUS
            reader, writer = ctx.nes_streams
            writer.write((get_payload(ctx) + "\n").encode())
            await asyncio.wait_for(writer.drain(), timeout=1.5)
            line = await asyncio.wait_for(reader.readline(), timeout=5)
            if not line:
                raise ConnectionResetError("The emulator disconnected")
            data = json.loads(line)
            auth = validate_connector(ctx, data)
            if not ctx.auth:
                ctx.auth = auth
                if ctx.awaiting_rom:
                    await ctx.server_auth(False)
            if data.get("overworldHC") is not None:
                ctx.overworld_item = data["overworldHC"]
            if data.get("overworldPB") is not None:
                ctx.armos_item = data["overworldPB"]
            if data.get("gameMode") == 19 and not ctx.finished_game:
                await ctx.send_msgs([{"cmd": "StatusUpdate", "status": 30}])
                ctx.finished_game = True
            for zone in ("overworld", "underworld1", "underworld2", "caves"):
                if zone in data:
                    await parse_locations(data[zone], ctx, False, zone)
            reconcile_shops(ctx)
            if ctx.nes_status != CONNECTION_CONNECTED_STATUS:
                logger.info("Successfully connected to NES")
                ctx.nes_status = CONNECTION_CONNECTED_STATUS
        except (OSError, TimeoutError, ValueError, KeyError, TypeError) as error:
            status = f"NES connection: {error}. Load {ctx.connector_script}"
            if ctx.nes_status != status:
                logger.info(status)
            ctx.nes_status = status
            ctx.connector_ready = False
            if ctx.nes_streams:
                ctx.nes_streams[1].close()
                ctx.nes_streams = None
            await asyncio.sleep(1)
    if ctx.nes_streams:
        ctx.nes_streams[1].close()
        ctx.nes_streams = None


async def run_game(romfile: str, auto_start: typing.Union[bool, str]) -> None:
    if auto_start is True:
        import webbrowser
        webbrowser.open(romfile)
    elif isinstance(auto_start, str) and os.path.isfile(auto_start):
        subprocess.Popen([auto_start, romfile],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


async def main(args):
    global DISPLAY_MSGS
    ctx = ZeldaContext(args.connect, args.password)
    ctx.connector_script = str(export_connector())
    logger.info("Load this Lua script in your emulator: %s", ctx.connector_script)
    game_settings = ctx.world_type.settings
    DISPLAY_MSGS = game_settings.display_msgs
    if args.diff_file:
        import Patch
        logging.info("Patch file was supplied. Creating nes rom..")
        meta, romfile = Patch.create_rom_file(args.diff_file)
        if "server" in meta:
            ctx.server_address = meta["server"]
        logging.info(f"Wrote rom file to {romfile}")
        async_start(run_game(romfile, game_settings.rom_start))
    ctx.server_task = asyncio.create_task(server_loop(ctx), name="ServerLoop")
    if gui_enabled and not getattr(args, "nogui", False):
        ctx.run_gui()
    ctx.run_cli()
    ctx.nes_sync_task = asyncio.create_task(nes_sync_task(ctx), name="NES Sync")

    await ctx.exit_event.wait()
    ctx.server_address = None

    await ctx.shutdown()

    if ctx.nes_sync_task:
        await ctx.nes_sync_task


def launch(*launch_args):
    """Run inside either the source or frozen Archipelago launcher."""
    import colorama

    Utils.init_logging("ZeldaAltClient")
    parser = get_base_parser(description="The Legend of Zelda (Alt) client")
    parser.add_argument('diff_file', default="", nargs="?", help="Path to an .aptlozalt patch")
    parser.add_argument('--export-connector', action='store_true', help="Export emulator scripts and exit")
    args = parser.parse_args(launch_args)
    if args.export_connector:
        print(export_connector())
        return
    if args.diff_file and not args.diff_file.lower().endswith('.aptlozalt'):
        parser.error("Expected an .aptlozalt patch")
    colorama.just_fix_windows_console()
    try:
        asyncio.run(main(args))
    finally:
        colorama.deinit()

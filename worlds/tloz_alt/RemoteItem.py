"""Draw other-world items with a custom sprite instead of a Rupee.

The base patch has already been applied when ``install_remote_item_sprite`` runs.
File offsets below are into that patched, headered US PRG0 ROM (131088 bytes).
They will not match a vanilla ROM: the base patch inserts bytes in PRG bank 1
and fixes up the RAM-code copy pointer, which slides this bank's file offsets.

Item id ``0x24`` is unused by the vanilla 0x00-0x23 pickup tables. Two hooks teach
the game what to do with it:

* Draw hook (bank 7 ``$E71E``, in ``AnimateItemObject``). For id ``$24`` only,
  borrow the fairy's item slot (``$14``) for one draw. That slot's sprite
  attribute is absolute palette row 2, the red / orange / white row the sprite
  was drawn for. The slot's CHR index in RAM (``$78FA`` after the base patch's
  +5 slide of the frame tables) is swapped to blank tile ``$1C`` for the call
  and then restored, so real fairies stay fairies.
* Take hook (RAM ``SetItemValue``, ROM file ``0x6C8F``). Id ``$24`` plays the
  usual item sound and lift, but does not write the inventory. The room-taken
  flag is already set before ``TakeItem``, which is what the Archipelago client
  watches. The vanilla remote-rupee path really did pay out one rupee.

Tile ``$1C`` is below the narrow-sprite test (``CMP #$20``), so that compare
becomes ``CMP #$1C``. Nothing in the frame table uses ``$1C``-``$1F`` except
this temporary swap. ``$1C``/``$1D`` are the blank 8x16 pair in common sprite
CHR (bank 2 ``$823F``); ``$1E``/``$1F`` are not blank and are left alone.

The code cave is the unused ``$FF`` run at bank 7 ``$FFC0``-``$FFEA``. ``$FFEB``
is the start of the "ZELDA" signature and must stay put. Bank 7 file offsets
are not moved by the base patch.
"""

from __future__ import annotations

# Low 6 bits, so shop / Take Any flag bits can still be OR'd on top.
REMOTE_ITEM_ID = 0x24

# Patched-ROM file offsets.
_DRAW_HOOK = 0x1E72E          # bank 7 $E71E: LDA ItemIdToDescriptor, X
_TAKE_HOOK = 0x6C8F           # SetItemValue: STA Items, Y
_NARROW_IMMEDIATE = 0x722D    # CMP #$20 inside Anim_WriteSpecificItemSprites
_FRAME_TABLE_LO = 0x721D      # low byte of the slid Anim_ItemFrameTiles pointer
_TILES = 0x824F               # bank 2 $823F, tiles $1C and $1D
_CAVE = 0x1FFD0               # bank 7 $FFC0

_DRAW_HOOK_VANILLA = bytes((0xBD, 0xC8, 0x72))
_TAKE_HOOK_VANILLA = bytes((0x99, 0x57, 0x06))

# 8x16, palette indexes 0 transparent / 1 red $16 / 2 orange $27 / 3 white $30.
# Top tile then bottom tile, NES 2bpp (plane 0, then plane 1).
_SPRITE_2BPP = bytes((
    0x18, 0x24, 0x42, 0xBD, 0x42, 0x24, 0x18, 0x18,
    0x00, 0x18, 0x24, 0x7E, 0x24, 0x18, 0x00, 0x18,
    0x18, 0x18, 0x24, 0x42, 0xBD, 0x42, 0x24, 0x18,
    0x18, 0x00, 0x18, 0x24, 0x7E, 0x24, 0x18, 0x00,
))


def _build_cave() -> tuple[bytes, int]:
    """Bank 7 cave. Returns the bytes and the take-hook entry offset."""
    code = bytearray()
    code += bytes((0xE0, REMOTE_ITEM_ID))          # CPX #$24
    bne_at = len(code)
    code += bytes((0xD0, 0x00))                    # BNE .normal
    code += bytes((0xAD, 0xFA, 0x78))              # LDA $78FA  fairy CHR index
    code += bytes((0x48,))                         # PHA
    code += bytes((0xA9, 0x1C))                    # LDA #$1C
    code += bytes((0x8D, 0xFA, 0x78))              # STA $78FA
    code += bytes((0xA2, 0x14))                    # LDX #$14  fairy slot
    code += bytes((0xA0, 0x14))                    # LDY #$14
    code += bytes((0x20, 0x3A, 0xE7))              # JSR DrawItemBySlot
    code += bytes((0x68,))                         # PLA
    code += bytes((0x8D, 0xFA, 0x78))              # STA $78FA
    code += bytes((0x60,))                         # RTS
    normal = len(code)
    code[bne_at + 1] = (normal - (bne_at + 2)) & 0xFF
    code += bytes((0xBD, 0xC8, 0x72))              # LDA ItemIdToDescriptor, X
    code += bytes((0x4C, 0x21, 0xE7))              # JMP $E721
    take_at = len(code)
    # X is still the item id. Skip the inventory write for the remote id only.
    code += bytes((0xE0, REMOTE_ITEM_ID))          # CPX #$24
    code += bytes((0xF0, 0x03))                    # BEQ .skip
    code += bytes((0x99, 0x57, 0x06))              # STA Items, Y
    code += bytes((0x60,))                         # RTS
    if len(code) > 0x2B:
        raise RuntimeError(f"remote-item cave is {len(code)} bytes; $FFC0 only has 43")
    return bytes(code), take_at


def install_remote_item_sprite(rom_data: bytearray) -> bytearray:
    """Patch CHR and the two hooks. Call this after the base bsdiff."""
    cave, take_at = _build_cave()
    take_addr = 0xFFC0 + take_at
    if take_addr > 0xFFEA:
        raise RuntimeError("remote-item take hook runs into the ZELDA signature")

    def expect(offset: int, expected: bytes, what: str) -> None:
        found = bytes(rom_data[offset:offset + len(expected)])
        if found != expected:
            raise RuntimeError(
                f"{what} at file ${offset:05X} is {found.hex()} , expected {expected.hex()}. "
                "The base patch layout may have changed."
            )

    expect(_DRAW_HOOK, _DRAW_HOOK_VANILLA, "AnimateItemObject descriptor load")
    expect(_TAKE_HOOK, _TAKE_HOOK_VANILLA, "SetItemValue store")
    expect(_NARROW_IMMEDIATE - 1, bytes((0xC9, 0x20)), "narrow-sprite compare")
    expect(_FRAME_TABLE_LO, bytes((0xE1, 0x78)), "slid item-frame table pointer")
    expect(_TILES, bytes(32), "blank CHR tiles $1C/$1D")
    expect(_CAVE, b"\xFF" * len(cave), "bank 7 code cave")

    rom_data[_DRAW_HOOK:_DRAW_HOOK + 3] = bytes((0x4C, 0xC0, 0xFF))  # JMP $FFC0
    rom_data[_TAKE_HOOK:_TAKE_HOOK + 3] = bytes((0x4C, take_addr & 0xFF, take_addr >> 8))
    rom_data[_NARROW_IMMEDIATE] = 0x1C
    rom_data[_TILES:_TILES + 32] = _SPRITE_2BPP
    rom_data[_CAVE:_CAVE + len(cave)] = cave
    return rom_data

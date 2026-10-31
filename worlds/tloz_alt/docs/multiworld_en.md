# The Legend of Zelda (Alt) Multiworld Setup Guide

## Required Software

- Archipelago 0.6.9 or newer and `tloz_alt.apworld`. The APWorld includes the client, emulator connector,
  Lua libraries, and supported BizHawk LuaSocket binaries; no custom Archipelago build is required.
- Mesen2 (tested with 2.1.1) or the BizHawk emulator. BizHawk versions 2.3.1 and higher are supported.
    - [BizHawk at TASVideos](https://tasvideos.org/BizHawk)
- Your legally acquired US v1.0 PRG0 ROM file, probably named `Legend of Zelda, The (U) (PRG0) [!].nes`

## Optional Software

- [Map Tracker](https://github.com/Br00ty/tloz_brooty/releases/latest)
    - Trackers must recognize the alternate game name, `The Legend of Zelda (Alt)`, to connect to this world.

## Installation Procedures

1. Install Archipelago, then use **Install APWorld** in its Launcher to install `tloz_alt.apworld`.
   Restart the Launcher after installation or an APWorld update.
    - Configure `tloz_alt_options.rom_file` in `host.yaml` with your original ROM path. Native TLoZ uses
      its separate `tloz_options` section; both may reference the same original ROM.
2. Assign Mesen2 or EmuHawk version 2.3.1 or higher as your default program for launching `.nes` files.
   Alternatively, set `tloz_alt_options.rom_start` in `host.yaml` to your emulator executable's full path.
    - Extract your BizHawk folder to your Desktop, or somewhere you will remember. Below are optional additional steps
       for loading ROMs more conveniently.
        1. Right-click on a ROM file and select **Open with...**
        2. Check the box next to **Always use this app to open .nes files**.
        3. Scroll to the bottom of the list and click the grey text **Look for another App on this PC**.
        4. Browse for `EmuHawk.exe` located inside your BizHawk folder (from step 1) and click **Open**.
3. (BizHawk only, EmuHawk version Ã¢â€°Â¤ 2.8) Go to Config > Customize. Switch to the Advanced tab, then switch the Lua Core from "NLua+KopiLua" to
  "Lua+LuaInterface". Then restart EmuHawk. This is required for the Lua script to function correctly.
  **NOTE: Even if "Lua+LuaInterface" is already selected, toggle between the two options and reselect it. Fresh installs** 
  **of newer versions of EmuHawk have a tendency to show "Lua+LuaInterface" as the default selected option but still load** 
  **"NLua+KopiLua" until this step is done.**

## Create a Config (.yaml) File

### What is a config file and why do I need one?

See the guide on setting up a basic YAML at the Archipelago setup
guide: [Basic Multiworld Setup Guide](/tutorial/Archipelago/setup/en)

### Where do I get a config file?

Use **Generate Template Options** in the Archipelago Launcher and select the generated template for
**The Legend of Zelda (Alt)**. Both `game:` and the game-options section must use that exact name. A webhost with
this world installed also exposes its [Player Options page](/games/The%20Legend%20of%20Zelda%20(Alt)/player-options).

### Verifying your config file

Validate or generate with an installation that includes this alternate world. A remote generator or validator
does not acquire the world merely because you installed it locally.

## Generating a Single-Player Game

1. Put your player YAML in `Players` and use **Generate** in the Archipelago Launcher.
2. Extract your `.aptlozalt` patch from the generated archive and use **Open Patch** in the Launcher.
3. The client selects the alternate world automatically, creates the ROM, and opens it according to
   `tloz_alt_options.rom_start` in `host.yaml`.
4. Host the generated archive and connect the client if you want persistent shop tracking or use starting items.

## Joining a MultiWorld Game

### Obtain your patch file and create your ROM

When you join a multiworld game, you will be asked to provide your config file to whoever is hosting. Once that is done,
the host will provide you with either a link to download your patch file, or with a zip file containing everyone's patch
files. Your patch file should have a `.aptlozalt` extension.

Use **Open Patch** in the Archipelago Launcher. If you installed the Windows file association, you can also double-click
the patch. The client creates your ROM in the same directory as the patch.


## Running the Client Program and Connecting to the Server

Once the Archipelago server has been hosted:

1. Select **Zelda 1 Client (Alt)** in the Launcher. From source, use
   `python Launcher.py "Zelda 1 Client (Alt)"`. Opening an `.aptlozalt` patch selects this client automatically.
   The client exports its connector bundle and prints the exact Lua path in its log.
   **Export Zelda 1 (Alt) Connector** in the Launcher also exports it and opens the containing folder.
2. Notice the `/connect command` on the server hosting page. (It should look like `/connect archipelago.gg:*****`
   where ***** are numbers)
3. Type the connect command into the client OR add the port to the pre-populated address on the top bar (it should
   already say `archipelago.gg`) and click `connect`.

### Running Your Game and Connecting to the Client Program

#### Mesen2

1. Open your patched `.nes` ROM in Mesen2.
2. Open Mesen's Script Window and enable script **network access** and **I/O/OS access** in its settings.
3. Load `connector_tloz_alt.lua` from the exported folder shown by the client and run it.
   Keep the exported files together. Mesen supplies its own `socket.core`; it does not use BizHawk's socket DLLs.
4. Start **Zelda 1 Client (Alt)** and connect it to your Archipelago room. Resume emulation if paused; communication
   runs on frame callbacks. The script log reports when the client connects.

The connector automatically detects Mesen2. It closes its TCP sockets when stopped and reconnects after a console
reset or loading a save state. Both emulators use port `52980`, so close the other emulator's connector first.

#### BizHawk

1. Open EmuHawk 2.3.1 or higher and load your ROM OR click your ROM file if it is already associated with the
   extension `*.nes`.
2. Use **Export Zelda 1 (Alt) Connector** in the Launcher, then drag the exported `connector_tloz_alt.lua`
   onto the main EmuHawk window. Keep its helper scripts and `x64`/`x86` folders beside it.
    1. You could instead open the Lua Console manually, click `Script` Ã¢Å’Âª `Open Script`, and navigate to
       `connector_tloz_alt.lua` with the file picker.
    2. If it gives a `NLua.Exceptions.LuaScriptException: .\socket.lua:13: module 'socket.core' not found:` exception
       close your emulator entirely, restart it and re-run these steps.
    3. If it says `Must use a version of BizHawk 2.3.1 or higher`, double-check your BizHawk version by clicking **
       Help** -> **About**.

### Updating the connector

After updating the APWorld, restart the client and load the script at the newly printed path. Exports are stored
under `tloz_alt/connectors/<version>-<content hash>` in Archipelago's writable user folder. Old exports remain
available, but the client detects incompatible protocol versions. A native TLoZ ROM is rejected before item writes;
a different seed or slot requires restarting the client. The Lua script must acknowledge the same ROM identity.

Mesen2 uses its bundled socket implementation. The supplied BizHawk binaries cover Windows x64 (Lua 5.1/5.4),
Windows x86 (Lua 5.1), and Linux x64 (Lua 5.1/5.4). Other platforms require a compatible LuaSocket binary.

## Play the game

When the client shows both NES and server are connected, you are good to go. You can check the connection status of the
NES at any time by running `/nes`.

### Other Client Commands

All other commands may be found on the [Archipelago Server and Client Commands Guide.](/tutorial/Archipelago/commands/en)
.

## Known Issues

- Triforce Fragments and Heart Containers may be purchased multiple times. It is up to you if you wish to take advantage
of this; logic will not account for or require purchasing any slot more than once. Remote items, no matter what they
are, will always only be sent once.
- Native and alternate Lua connectors use the same TCP port, `52980`. Run one emulator/client pair at a time.
- Native and alternate slots can exchange items normally, but cannot share an ItemLink group because they are
registered as different games.
- Whether you've purchased from a shop is tracked via Archipelago between sessions: if you revisit a single player game,
none of your shop pruchase statuses will be remembered. If you want them to be, connect to the client and server like 
you would in a multiplayer game.

## Building from source

Run these commands from the project root using its configured Python environment:

```text
python Launcher.py "Build APWorlds" -- "The Legend of Zelda (Alt)" --skip_open_folder
python setup.py build_exe --yes
```

The first command writes `build/apworlds/tloz_alt.apworld`. Distribute this file alone; users export the bundled
connector through the client or Launcher. The second command is optional and builds the entire application.
The source world is discovered automatically, so packaging is optional for local development.

To export scripts without opening the client UI:

```text
python Launcher.py "Zelda 1 Client (Alt)" -- --export-connector
```

Application builds made from this updated source retain `ArchipelagoZelda1Client.exe --alt` and the `.aptlozalt`
Windows association; they forward to the world-local client. Older custom executables need rebuilding to get that
forwarding change. Installing the new APWorld alone is sufficient when using the Launcher's **Open Patch** or
**Zelda 1 Client (Alt)** entry, including on stock installations.

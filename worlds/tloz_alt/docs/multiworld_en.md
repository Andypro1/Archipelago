# The Legend of Zelda (Alt) Multiworld Setup Guide

## Required Software

- This project's Zelda1Client with alternate-world support, the `tloz_alt` world, and `connector_tloz_alt.lua`.
    - A standalone `.apworld` does not include the updated client or Lua connector. Use this project's application
      build or run its client from source.
- Mesen2 (tested with 2.1.1) or the BizHawk emulator. BizHawk versions 2.3.1 and higher are supported.
    - [BizHawk at TASVideos](https://tasvideos.org/BizHawk)
- Your legally acquired US v1.0 PRG0 ROM file, probably named `Legend of Zelda, The (U) (PRG0) [!].nes`

## Optional Software

- [Map Tracker](https://github.com/Br00ty/tloz_brooty/releases/latest)
    - Trackers must recognize the alternate game name, `The Legend of Zelda (Alt)`, to connect to this world.

## Installation Procedures

1. Install this project's application build or prepare its configured Python environment.
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
3. (BizHawk only, EmuHawk version ≤ 2.8) Go to Config > Customize. Switch to the Advanced tab, then switch the Lua Core from "NLua+KopiLua" to
  "Lua+LuaInterface". Then restart EmuHawk. This is required for the Lua script to function correctly.
  **NOTE: Even if "Lua+LuaInterface" is already selected, toggle between the two options and reselect it. Fresh installs** 
  **of newer versions of EmuHawk have a tendency to show "Lua+LuaInterface" as the default selected option but still load** 
  **"NLua+KopiLua" until this step is done.**

## Create a Config (.yaml) File

### What is a config file and why do I need one?

See the guide on setting up a basic YAML at the Archipelago setup
guide: [Basic Multiworld Setup Guide](/tutorial/Archipelago/setup/en)

### Where do I get a config file?

Use **Generate Template Options** in this project's Launcher and select the generated template for
**The Legend of Zelda (Alt)**. Both `game:` and the game-options section must use that exact name. A webhost with
this world installed also exposes its [Player Options page](/games/The%20Legend%20of%20Zelda%20(Alt)/player-options).

### Verifying your config file

Validate or generate with an installation that includes this alternate world. A remote generator or validator
does not acquire the world merely because you installed it locally.

## Generating a Single-Player Game

1. Put your player YAML in `Players` and use **Generate** in this project's Launcher.
2. Extract your `.aptlozalt` patch from the generated archive and use **Open Patch** in the Launcher.
3. The client selects the alternate world automatically, creates the ROM, and opens it according to
   `tloz_alt_options.rom_start` in `host.yaml`.
4. Host the generated archive and connect the client if you want persistent shop tracking or use starting items.

## Joining a MultiWorld Game

### Obtain your patch file and create your ROM

When you join a multiworld game, you will be asked to provide your config file to whoever is hosting. Once that is done,
the host will provide you with either a link to download your patch file, or with a zip file containing everyone's patch
files. Your patch file should have a `.aptlozalt` extension.

Use **Open Patch** in this project's Launcher. If you installed the Windows file association, you can also double-click
the patch. The client creates your ROM in the same directory as the patch.


## Running the Client Program and Connecting to the Server

Once the Archipelago server has been hosted:

1. Select **Zelda 1 Client (Alt)** in the Launcher, or run `ArchipelagoZelda1Client.exe --alt`.
   From source, use `python Zelda1Client.py --alt`. Opening a `.aptlozalt` patch selects the alternate world automatically.
2. Notice the `/connect command` on the server hosting page. (It should look like `/connect archipelago.gg:*****`
   where ***** are numbers)
3. Type the connect command into the client OR add the port to the pre-populated address on the top bar (it should
   already say `archipelago.gg`) and click `connect`.

### Running Your Game and Connecting to the Client Program

#### Mesen2

1. Open your patched `.nes` ROM in Mesen2.
2. Open Mesen's Script Window and enable script **network access** and **I/O/OS access** in its settings.
3. Load `data/lua/connector_tloz_alt.lua` from the Archipelago folder and run it. Keep `json.lua` and
   `lua_5_3_compat.lua` beside it. Mesen supplies its own `socket.core`; it does not use BizHawk's socket DLLs.
4. Start **Zelda 1 Client (Alt)** and connect it to your Archipelago room. Resume emulation if paused; communication
   runs on frame callbacks. The script log reports when the client connects.

The connector automatically detects Mesen2. It closes its TCP sockets when stopped and reconnects after a console
reset or loading a save state. Both emulators use port `52980`, so close the other emulator's connector first.

#### BizHawk

1. Open EmuHawk 2.3.1 or higher and load your ROM OR click your ROM file if it is already associated with the
   extension `*.nes`.
2. Navigate to where you installed Archipelago, then to `data/lua`, and drag+drop the `connector_tloz_alt.lua` script onto
   the main EmuHawk window.
    1. You could instead open the Lua Console manually, click `Script` 〉 `Open Script`, and navigate to
       `connector_tloz_alt.lua` with the file picker.
    2. If it gives a `NLua.Exceptions.LuaScriptException: .\socket.lua:13: module 'socket.core' not found:` exception
       close your emulator entirely, restart it and re-run these steps.
    3. If it says `Must use a version of BizHawk 2.3.1 or higher`, double-check your BizHawk version by clicking **
       Help** -> **About**.

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

The first command writes `build/apworlds/tloz_alt.apworld`; distribute the updated client and Lua connector with it.
The second builds the application, including both worlds and both connectors, under `build/exe.<platform>-<python>`.
The source world is discovered automatically, so packaging is optional for local development.

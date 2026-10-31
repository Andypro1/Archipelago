"""Register the packaged client without requiring a separate executable."""
from worlds.LauncherComponents import Component, SuffixIdentifier, Type, components, launch


def launch_client(*args: str) -> None:
    from .Client import launch as launch_alt
    launch(launch_alt, name="ZeldaAltClient", args=args)


def export_scripts(*args: str) -> None:
    from .connector_resources import export_connector
    from worlds.LauncherComponents import open_folder
    script = export_connector()
    print(f"Load this Lua script in Mesen2 or BizHawk: {script}")
    if "--skip_open_folder" not in args:
        open_folder(str(script.parent))


# Reuse the legacy entry in custom builds; stock installations get the same entry from this APWorld.
component = next((entry for entry in components if entry.display_name == "Zelda 1 Client (Alt)"), None)
if component is None:
    component = Component("Zelda 1 Client (Alt)", component_type=Type.CLIENT,
                          game_name="The Legend of Zelda (Alt)", file_identifier=SuffixIdentifier(".aptlozalt"))
    components.append(component)
component.func = launch_client

components.append(Component("Export Zelda 1 (Alt) Connector", func=export_scripts, component_type=Type.TOOL,
                            description="Export the bundled Lua scripts for Mesen2 or BizHawk."))

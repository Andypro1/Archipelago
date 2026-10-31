"""Export emulator resources from either a source folder or an installed APWorld."""
import hashlib
import json
from pathlib import Path
from pkgutil import get_data

from Utils import user_path


RESOURCE_FILES = (
    "connector_tloz_alt.lua", "json.lua", "json.LICENSE.txt", "common.lua", "socket.lua", "lua_5_3_compat.lua",
    "x64/luasocket.LICENSE.txt", "x64/socket-linux-5-1.so", "x64/socket-linux-5-4.so",
    "x64/socket-windows-5-1.dll", "x64/socket-windows-5-4.dll",
    "x86/luasocket.LICENSE.txt", "x86/socket-windows-5-1.dll",
)


def export_connector(directory: Path | None = None) -> Path:
    """Return a real Lua path; isolate different bundles so loaded DLLs need not be overwritten."""
    resources = {name: get_data(__package__, f"data/lua/{name}") for name in RESOURCE_FILES}
    if any(data is None for data in resources.values()):
        raise FileNotFoundError("The Zelda (Alt) APWorld is missing connector resources. Reinstall the APWorld.")
    if directory is None:
        version = json.loads(get_data(__package__, "archipelago.json"))["world_version"]
        digest = hashlib.sha256(b"".join(resources.values())).hexdigest()[:12]
        directory = Path(user_path("tloz_alt", "connectors", f"{version}-{digest}"))
    for name, data in resources.items():
        destination = directory / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.is_file() or destination.read_bytes() != data:
            destination.write_bytes(data)
    return (directory / "connector_tloz_alt.lua").resolve()

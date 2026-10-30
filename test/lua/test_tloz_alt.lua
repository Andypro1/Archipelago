-- Run through test.programs.test_tloz_alt_connector with Mesen's --testRunner.
-- Uses real Mesen memory and loopback TCP. BizHawk cases adapt its APIs to Mesen.
local mesen = emu
local realSocket = require("socket.core")
local root, output, backend = TEST_ROOT, TEST_OUTPUT, TEST_BACKEND
package.path = root .. "/data/lua/?.lua;" .. package.path
local json = require("json")
local callbacks, receivedColors = {}, {}
local peer, listener, script
local acceptedClosed = 0

local function wrapSocket(sock)
    return setmetatable({}, {__index = function(_, key)
        if key == "accept" then
            return function()
                local connection, err = sock:accept()
                return connection and wrapSocket(connection), err
            end
        elseif key == "send" then
            return function(_, data, first)
                -- Force partial writes while still putting real bytes on the wire.
                local sent, err, last = sock:send(data, first, math.min(first + 36, #data))
                if sent and sent < #data then return nil, "timeout", sent end
                return sent, err, last
            end
        elseif key == "close" then
            return function() acceptedClosed = acceptedClosed + 1; return sock:close() end
        end
        return function(_, ...) return sock[key](sock, ...) end
    end})
end
local sockets = {tcp = function()
    listener = assert(realSocket.tcp())
    return wrapSocket(listener)
end}

local function tick()
    if backend == "Mesen2" then
        callbacks[mesen.eventType.endFrame]()
    else
        local ok, err = coroutine.resume(script)
        assert(ok, err)
    end
end
local function ram(address) return mesen.read(address, mesen.memType.nesInternalRam, false) end
local function write(address, value) mesen.write(address, value, mesen.memType.nesInternalRam) end
local function connect()
    peer = assert(realSocket.tcp())
    peer:settimeout(1)
    assert(peer:connect("127.0.0.1", 52980))
    peer:settimeout(0)
    for _ = 1, 60 do tick() end
end
local function response()
    local partial = ""
    for _ = 1, 10000 do
        tick()
        local line, err, part = peer:receive("*l", partial)
        if line then return json.decode(line) end
        assert(err == "timeout", err)
        partial = part or ""
    end
    error("Timed out receiving connector response")
end
local function exchange(block)
    assert(peer:send(json.encode(block) .. "\n"))
    return response()
end
local function test()
    package.loaded["socket.core"] = sockets
    if backend == "Mesen2" then
        local originalDraw = mesen.drawString
        emu = setmetatable({
            addEventCallback = function(fn, eventType) callbacks[eventType] = fn end,
            drawString = function(x, y, text, color, background)
                receivedColors[color] = true
                originalDraw(x, y, text, color, background)
            end,
        }, {__index = mesen})
        dofile(root .. "/data/lua/connector_tloz_alt.lua")
        assert(callbacks[mesen.eventType.reset] and callbacks[mesen.eventType.stateLoaded])
        tick()
        assert(receivedColors[0xFF0000], "Mesen red text must be opaque, not transparent")
    else
        bit = {}
        package.loaded.socket = {socket = sockets}
        local domain = mesen.memType.nesInternalRam
        local domains = {RAM=mesen.memType.nesInternalRam, WRAM=mesen.memType.nesSaveRam,
                         ["Battery RAM"]=mesen.memType.nesSaveRam, ["PRG ROM"]=mesen.memType.nesPrgRom}
        memory = {
            getmemorydomainlist = function() return {backend == "QuickNES" and "WRAM" or "System Bus"} end,
            usememorydomain = function(name) domain = assert(domains[name]) end,
            read_u8 = function(address) return mesen.read(address, domain, false) end,
            write_u8 = function(address, value) mesen.write(address, value, domain) end,
            readbyterange = function(address, length)
                local bytes = {}
                for i = 0, length - 1 do bytes[i] = mesen.read(address + i, domain, false) end
                return bytes
            end,
        }
        client = {getversion=function() return "2.9" end, screenwidth=function() return 256 end}
        gui = {drawText=function() end, drawEllipse=function() end}
        event = {onexit=function(fn) callbacks[mesen.eventType.scriptEnded] = fn end}
        emu = {frameadvance=function() coroutine.yield() end}
        script = coroutine.create(function() dofile(root .. "/data/lua/connector_tloz_alt.lua") end)
        tick()
    end

    -- Controlled memory fixtures: assertions run before emulation advances.
    for address = 0, 0x7FF do write(address, 0) end
    for address = 0, 0x1FFF do mesen.write(address, 0, mesen.memType.nesSaveRam) end
    local name = "ZeldaAlternateLongPlayerName"
    for i = 0, 31 do mesen.write(0x20 + i, name:byte(i + 1) or 0, mesen.memType.nesPrgRom) end
    connect()
    local block = {items={7123, 7127, 7100, 7130, 7124}, bonusItems={7110},
                   shops={left=0x20, middle=0x04, right=0x10}, messages={test="A message"}}
    local before = exchange(block)
    assert(before.itemsObtained == 0 and ram(0x628) == 0, "Do not grant items on title/file screens")
    write(0x12, 5)
    write(0x67C, 8)
    write(0x505, 0x24)
    write(0x506, 9)
    write(0x680, 0x10); write(0x700, 0x10); write(0x780, 0x10)
    local wire = json.encode(block) .. "\n"
    assert(peer:send(wire:sub(1, 19)))
    for _ = 1, 5 do tick() end
    assert(ram(0x677) == 0, "Partial JSON must not grant items")
    assert(peer:send(wire:sub(20)))
    local result = response()
    assert(result.itemsObtained == 5 and ram(0x67A) == 1, "Ring bonus must not corrupt item counters")
    assert(ram(0x658) == 4 and ram(0x674) == 1 and ram(0x67D) == 1)
    assert(ram(0x662) == 2 and ram(0x671) == 1)
    assert(mesen.read(0xB92, mesen.memType.nesSaveRam, false) == 0x16)
    assert(mesen.read(0x6B92, mesen.memType.nesDebug, false) == 0x16)
    assert(mesen.read(0x804, mesen.memType.nesSaveRam, false) == 0x16)
    assert(ram(0x505) == 0x24 and ram(0x506) == 9, "Incoming items must leave the room pickup alone")
    assert(#result.playerName == 32 and string.char(table.unpack(result.playerName)):sub(1, #name) == name)
    assert(#result.overworld == 128 and result.overworld[2] == 0x10)
    assert(#result.underworld1 == 128 and result.underworld1[2] == 0x10)
    assert(#result.underworld2 == 128 and result.underworld2[2] == 0x10)
    assert(result.caves.slot1 == 0x20 and result.caves.slot2 == 0x04 and result.caves.slot3 == 0x10)
    assert(result.overworldHC == mesen.read(0x1789A, mesen.memType.nesPrgRom, false))
    assert(result.overworldPB == mesen.read(0x10CB2, mesen.memType.nesPrgRom, false))
    exchange(block)
    assert(ram(0x658) == 4 and ram(0x67D) == 1, "Repeated payload must not duplicate items")
    write(0x12, 19)
    assert(exchange({}).gameMode == 19)

    -- Disconnect, reconnect, and recover after malformed JSON.
    peer:close(); tick(); connect()
    write(0x12, 5)
    assert(exchange({}).gameMode == 5)
    assert(peer:send("not JSON\n")); tick(); peer:close(); connect()
    assert(exchange({}).itemsObtained == 5)
    if backend == "Mesen2" then
        for _, kind in ipairs({mesen.eventType.reset, mesen.eventType.stateLoaded}) do
            local closed = acceptedClosed
            callbacks[kind]()
            assert(acceptedClosed == closed + 1)
            peer:close(); connect()
            assert(exchange({}).gameMode == 5)
        end
    end
    local closed = acceptedClosed
    callbacks[mesen.eventType.scriptEnded]()
    assert(acceptedClosed == closed + 2, "Shutdown must release the peer and listening sockets")
end

local ok, err = pcall(test)
if peer then peer:close() end
if listener then listener:close() end
emu = mesen
local file = assert(io.open(output, "w"))
file:write(ok and (backend .. ": passed") or tostring(err))
file:close()
mesen.addEventCallback(function() mesen.stop(ok and 0 or 1) end, mesen.eventType.endFrame)

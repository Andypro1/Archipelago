--Shamelessly based off the FF1 lua

local isMesen = emu and emu.addEventCallback ~= nil
-- Mesen does not set the working directory to the script's directory.
local scriptDirectory = debug.getinfo(1, "S").source:match("^@(.+[/\\])")
if scriptDirectory then package.path = scriptDirectory .. "?.lua;" .. package.path end
local json = require("json")
-- Mesen supplies LuaSocket itself; do not load BizHawk's socket DLL into it.
local socket = isMesen and require("socket.core") or require("socket").socket
local log = isMesen and emu.log or print
local u8, wU8, uRange, drawText, drawMessages, itemMessages
local memDomain = {}

if isMesen then
    bit = bit or {}
    require("lua_5_3_compat")
    local domain = emu.memType.nesInternalRam
    memDomain.ram = function() domain = emu.memType.nesInternalRam end
    memDomain.saveram = function() domain = emu.memType.nesSaveRam end
    memDomain.rom = function() domain = emu.memType.nesPrgRom end
    u8 = function(address) return emu.read(address, domain, false) end
    wU8 = function(address, value) emu.write(address, value, domain) end
    uRange = function(address, length)
        local bytes = {}
        for i = 0, length - 1 do bytes[i] = u8(address + i) end
        return bytes
    end
    drawText = function(x, y, message, color)
        -- Mesen's ARGB alpha is inverted: zero is opaque.
        color = color % 0x1000000 + (255 - math.floor(color / 0x1000000)) * 0x1000000
        emu.drawString(x, y, message, color, 0x4F000000)
    end
    itemMessages = {}
    drawMessages = function()
        local y = 10
        for _, message in pairs(itemMessages) do
            if message.TTL > 0 then
                for i = 1, #message.message, 40 do
                    drawText(5, y, message.message:sub(i, i + 39), message.color)
                    y = y + 16
                end
                message.TTL = message.TTL - 1
            end
        end
    end
else
    require("common")
    if not checkBizHawkVersion() then return end
    u8, wU8, uRange = memory.read_u8, memory.write_u8, memory.readbyterange
    drawText, drawMessages, itemMessages = _G.drawText, _G.drawMessages, _G.itemMessages
    local domains = memory.getmemorydomainlist()
    local saveDomain = domains[1] == "WRAM" and "WRAM" or "Battery RAM"
    memDomain.ram = function() memory.usememorydomain("RAM") end
    memDomain.saveram = function() memory.usememorydomain(saveDomain) end
    memDomain.rom = function() memory.usememorydomain("PRG ROM") end
end

local function drawStatus(color)
    if isMesen then
        emu.drawRectangle(248, 9, 6, 6, color % 0x1000000, true)
    else
        gui.drawEllipse(248, 9, 6, 6, "Black", color)
    end
end
local STATE_OK = "Ok"
local STATE_TENTATIVELY_CONNECTED = "Tentatively Connected"
local STATE_INITIAL_CONNECTION_MADE = "Initial Connection Made"
local STATE_UNINITIALIZED = "Uninitialized"

local consumableStacks = nil
local curstate =  STATE_UNINITIALIZED
local zeldaSocket = nil
local frame = 0
local gameMode = 0

local cave_index
local triforce_byte
local game_state

local shopsChecked = {}
local shopSlotLeft       = 0x0628
local shopSlotMiddle     = 0x0629
local shopSlotRight      = 0x062A

--N.B.: you won't find these in a RAM map. They're flag values that the base patch derives from the cave ID.
local blueRingShopBit       = 0x40
local potionShopBit         = 0x02
local arrowShopBit          = 0x08
local candleShopBit         = 0x10
local shieldShopBit         = 0x20
local takeAnyCaveBit        = 0x01


local sword                 = 0x0657
local bombs                 = 0x0658
local maxBombs              = 0x067C
local keys                  = 0x066E
local arrow                 = 0x0659
local bow                   = 0x065A
local candle                = 0x065B
local recorder              = 0x065C
local food                  = 0x065D
local waterOfLife           = 0x065E
local magicalRod            = 0x065F
local raft                  = 0x0660
local bookOfMagic           = 0x0661
local ring                  = 0x0662
local stepladder            = 0x0663
local magicalKey            = 0x0664
local powerBracelet         = 0x0665
local letter                = 0x0666
local clockItem             = 0x066C
local heartContainers       = 0x066F
local partialHearts         = 0x0670
local triforceFragments     = 0x0671
local boomerang             = 0x0674
local magicalBoomerang      = 0x0675
local magicalShield         = 0x0676
local rupeesToAdd           = 0x067D
local rupeesToSubtract      = 0x067E
local itemsObtained         = 0x0677
local takeAnyCavesChecked   = 0x0678
local localTriforce         = 0x0679
local bonusItemsObtained    = 0x067A
local itemsObtainedHigh     = 0x067B

itemAPids = {
    ["Boomerang"] = 7100,
    ["Bow"] = 7101,
    ["Magical Boomerang"] = 7102,
    ["Raft"] = 7103,
    ["Stepladder"] = 7104,
    ["Recorder"] = 7105,
    ["Magical Rod"] = 7106,
    ["Red Candle"] = 7107,
    ["Book of Magic"] = 7108,
    ["Magical Key"] = 7109,
    ["Red Ring"] = 7110,
    ["Silver Arrow"] = 7111,
    ["Sword"] = 7112,
    ["White Sword"] = 7113,
    ["Magical Sword"] = 7114,
    ["Heart Container"] = 7115,
    ["Letter"] = 7116,
    ["Magical Shield"] = 7117,
    ["Candle"] = 7118,
    ["Arrow"] = 7119,
    ["Food"] = 7120,
    ["Water of Life (Blue)"] = 7121,
    ["Water of Life (Red)"] = 7122,
    ["Blue Ring"] = 7123,
    ["Triforce Fragment"] = 7124,
    ["Power Bracelet"] = 7125,
    ["Small Key"] = 7126,
    ["Bomb"] = 7127,
    ["Recovery Heart"] = 7128,
    ["Five Rupees"] = 7129,
    ["Rupee"] = 7130,
    ["Clock"] = 7131,
    ["Fairy"] = 7132
}


itemIDNames = {}

for key, value in pairs(itemAPids) do
    itemIDNames[value] = key
end

local function getItemsObtained()
    memDomain.ram()
    return bit.bor(bit.lshift(u8(itemsObtainedHigh), 8), u8(itemsObtained))
end

local function setItemsObtained(value)
    memDomain.ram()
    wU8(itemsObtainedHigh, bit.rshift(value, 8))
    wU8(itemsObtained, bit.band(value, 0xFF))
end

local function determineItem(array)
    memdomain.ram()
    currentItemsObtained = getItemsObtained()
    
end

local function gotSword()
    local currentSword = u8(sword)
    wU8(sword, math.max(currentSword, 1))
end

local function gotWhiteSword()
    local currentSword = u8(sword)
    wU8(sword, math.max(currentSword, 2))
end

local function gotMagicalSword()
    wU8(sword, 3)
end

local function gotBomb()
    local currentBombs = u8(bombs)
    local currentMaxBombs = u8(maxBombs)
    wU8(bombs, math.min(currentBombs + 4, currentMaxBombs))
end

local function gotArrow()
    local currentArrow = u8(arrow)
    wU8(arrow, math.max(currentArrow, 1))
end

local function gotSilverArrow()
    wU8(arrow, 2)
end

local function gotBow()
    wU8(bow, 1)
end

local function gotCandle()
    local currentCandle = u8(candle)
    wU8(candle, math.max(currentCandle, 1))
end

local function gotRedCandle()
    wU8(candle, 2)
end

local function gotRecorder()
    wU8(recorder, 1)
end

local function gotFood()
    wU8(food, 1)
end

local function gotWaterOfLifeBlue()
    local currentWaterOfLife = u8(waterOfLife)
    wU8(waterOfLife, math.max(currentWaterOfLife, 1))
end

local function gotWaterOfLifeRed()
    wU8(waterOfLife, 2)
end

local function gotMagicalRod()
    wU8(magicalRod, 1)
end

local function gotBookOfMagic()
    wU8(bookOfMagic, 1)
end

local function gotRaft()
    wU8(raft, 1)
end

local function gotBlueRing()
    local currentRing = u8(ring)
    wU8(ring, math.max(currentRing, 1))
    memDomain.saveram()
    local currentTunicColor = u8(0x0B92)
    if currentTunicColor == 0x29 then 
        wU8(0x0B92, 0x32)
        wU8(0x0804, 0x32)
    end
end

local function gotRedRing()
    wU8(ring, 2)
    memDomain.saveram()
    wU8(0x0B92, 0x16)
    wU8(0x0804, 0x16)
end

local function gotStepladder()
    wU8(stepladder, 1)
end

local function gotMagicalKey()
    wU8(magicalKey, 1)
end

local function gotPowerBracelet()
    wU8(powerBracelet, 1)
end

local function gotLetter()
    wU8(letter, 1)
end

local function gotHeartContainer()
    local currentHeartContainers = bit.rshift(bit.band(u8(heartContainers), 0xF0), 4)
    if currentHeartContainers < 16 then
        currentHeartContainers = math.min(currentHeartContainers + 1, 16)
        local currentHearts = bit.band(u8(heartContainers), 0x0F) + 1
        wU8(heartContainers, bit.lshift(currentHeartContainers, 4) + currentHearts)
    end
end

local function gotTriforceFragment()
    local triforceByte = 0xFF
    local newTriforceCount = u8(localTriforce) + 1
    wU8(localTriforce, newTriforceCount)
end

local function gotBoomerang()
    wU8(boomerang, 1)
end

local function gotMagicalBoomerang()
    wU8(magicalBoomerang, 1)
end

local function gotMagicalShield()
    wU8(magicalShield, 1)
end

local function gotRecoveryHeart()
    local currentHearts = bit.band(u8(heartContainers), 0x0F)
    local currentHeartContainers = bit.rshift(bit.band(u8(heartContainers), 0xF0), 4)
    if currentHearts < currentHeartContainers then 
        currentHearts = currentHearts + 1 
    else
        wU8(partialHearts, 0xFF)
    end
    currentHearts = bit.bor(bit.band(u8(heartContainers), 0xF0), currentHearts)
    wU8(heartContainers, currentHearts)
end

local function gotFairy()
    local currentHearts = bit.band(u8(heartContainers), 0x0F)
    local currentHeartContainers = bit.rshift(bit.band(u8(heartContainers), 0xF0), 4)
    if currentHearts < currentHeartContainers then 
        currentHearts = currentHearts + 3
        if currentHearts > currentHeartContainers then
            currentHearts = currentHeartContainers
            wU8(partialHearts, 0xFF)
        end
    else
        wU8(partialHearts, 0xFF)
    end
    currentHearts = bit.bor(bit.band(u8(heartContainers), 0xF0), currentHearts)
    wU8(heartContainers, currentHearts)
end

local function gotClock()
    wU8(clockItem, 1)
end

local function gotFiveRupees()
    local currentRupeesToAdd = u8(rupeesToAdd)
    wU8(rupeesToAdd, math.min(currentRupeesToAdd + 5, 255))
end

local function gotSmallKey()
    wU8(keys, math.min(u8(keys) + 1, 9))
end

local function gotItem(item)
    -- Grant the inventory bits only. Do not write itemToLift ($0505) or
    -- itemLiftTimer ($0506): that slot is the live room item, so the old
    -- "hold it over Link's head" cue stole whatever pickup was on screen.
    -- The other player's send is already drawn by drawMessages().
    local itemName = itemIDNames[item]
    if not itemName then return end
    wU8(0x602, 4)
    local numberObtained = getItemsObtained() + 1
    setItemsObtained(numberObtained)
    if itemName == "Boomerang" then gotBoomerang() end
    if itemName == "Bow" then gotBow() end
    if itemName == "Magical Boomerang" then gotMagicalBoomerang() end
    if itemName == "Raft" then gotRaft() end
    if itemName == "Stepladder" then gotStepladder() end
    if itemName == "Recorder" then gotRecorder() end
    if itemName == "Magical Rod" then gotMagicalRod() end
    if itemName == "Red Candle" then gotRedCandle() end
    if itemName == "Book of Magic" then gotBookOfMagic() end
    if itemName == "Magical Key" then gotMagicalKey() end
    if itemName == "Red Ring" then gotRedRing() end
    if itemName == "Silver Arrow" then gotSilverArrow() end
    if itemName == "Sword" then gotSword() end
    if itemName == "White Sword" then gotWhiteSword() end
    if itemName == "Magical Sword" then gotMagicalSword() end
    if itemName == "Heart Container" then gotHeartContainer() end
    if itemName == "Letter" then gotLetter() end
    if itemName == "Magical Shield" then gotMagicalShield() end
    if itemName == "Candle" then gotCandle() end
    if itemName == "Arrow" then gotArrow() end
    if itemName == "Food" then gotFood() end
    if itemName == "Water of Life (Blue)" then gotWaterOfLifeBlue() end
    if itemName == "Water of Life (Red)" then gotWaterOfLifeRed() end
    if itemName == "Blue Ring" then gotBlueRing() end
    if itemName == "Triforce Fragment" then gotTriforceFragment() end
    if itemName == "Power Bracelet" then gotPowerBracelet() end
    if itemName == "Small Key" then gotSmallKey() end
    if itemName == "Bomb" then gotBomb() end
    if itemName == "Recovery Heart" then gotRecoveryHeart() end
    if itemName == "Five Rupees" then gotFiveRupees() end
    if itemName == "Rupee" then wU8(rupeesToAdd, math.min(u8(rupeesToAdd) + 1, 255)) end
    if itemName == "Fairy" then gotFairy() end
    if itemName == "Clock" then gotClock() end
    memDomain.ram()
end


local function StateOKForMainLoop()
    memDomain.ram()
    local gameMode = u8(0x12) 
    return gameMode == 5 
end

local function checkCaveItemObtained()
    memDomain.ram() 
    local returnTable = {}
    returnTable["slot1"] = u8(shopSlotLeft)
    returnTable["slot2"] = u8(shopSlotMiddle)
    returnTable["slot3"] = u8(shopSlotRight)
    returnTable["takeAnys"] = u8(takeAnyCavesChecked)
    return returnTable
end

function generateOverworldLocationChecked()
    memDomain.ram()
    data = uRange(0x067E, 0x81)
    data[0] = nil
    return data
end

function getHCLocation()
    memDomain.rom()
    data = u8(0x1789A)
    return data
end

function getPBLocation()
    memDomain.rom()
    data = u8(0x10CB2)
    return data
end

function generateUnderworld16LocationChecked()
    memDomain.ram()
    data = uRange(0x06FE, 0x81)
    data[0] = nil
    return data
end

function generateUnderworld79LocationChecked()
    memDomain.ram()
    data = uRange(0x077E, 0x81)
    data[0] = nil
    return data
end

function updateTriforceFragments()
    memDomain.ram()
    local triforceByte = 0xFF
    totalTriforceCount = u8(localTriforce)
    local currentPieces = bit.rshift(triforceByte, 8 - math.min(8, totalTriforceCount))
    wU8(triforceFragments, currentPieces)
end

function processBlock(block)
    if block ~= nil then
        local msgBlock = block['messages']
        if msgBlock ~= nil then
            for i, v in pairs(msgBlock) do
                if itemMessages[i] == nil then
                    local msg = {TTL=450, message=v, color=0xFFFF0000}
                    itemMessages[i] = msg
                end
            end
        end
        local isInGame = StateOKForMainLoop()
        local bonusItems = block["bonusItems"]
        if bonusItems ~= nil and isInGame then
            for i, item in ipairs(bonusItems) do
                memDomain.ram()
                if i > u8(bonusItemsObtained) then
                    gotItem(item)
                    setItemsObtained(getItemsObtained() - 1)
                    wU8(bonusItemsObtained, u8(bonusItemsObtained) + 1)
                end
            end
        end
        local itemsBlock = block["items"]
        memDomain.ram()
        if itemsBlock ~= nil and isInGame then
            memDomain.ram()
            --get item from item code
            --get function from item
            --do function
            for i, item in ipairs(itemsBlock) do
                memDomain.ram()
                if i > getItemsObtained() then
                    gotItem(item)
                end
            end
        end
        local shopsBlock = block["shops"]
        if isInGame then updateTriforceFragments() end
        memDomain.ram()
        if shopsBlock ~= nil and isInGame then
            wU8(shopSlotLeft, bit.bor(u8(shopSlotLeft), shopsBlock["left"]))
            wU8(shopSlotMiddle, bit.bor(u8(shopSlotMiddle), shopsBlock["middle"]))
            wU8(shopSlotRight, bit.bor(u8(shopSlotRight), shopsBlock["right"]))
        end
    end
end

local server
local incoming, outgoing = "", ""
local sendIndex = 1

local function disconnect(reason)
    if zeldaSocket then zeldaSocket:close() end
    zeldaSocket = nil
    incoming, outgoing, sendIndex = "", "", 1
    curstate = STATE_UNINITIALIZED
    gameMode = 0
    if reason then log(reason) end
end

local function closeSockets()
    disconnect()
    if server then server:close(); server = nil end
end

local function sendResponse()
    local sent, err, last = zeldaSocket:send(outgoing, sendIndex)
    sendIndex = (sent or last or (sendIndex - 1)) + 1
    if err and err ~= "timeout" then disconnect("Send failed: " .. err); return end
    if sendIndex <= #outgoing then return end
    outgoing, sendIndex = "", 1
    if curstate == STATE_INITIAL_CONNECTION_MADE then
        curstate = STATE_TENTATIVELY_CONNECTED
    elseif curstate == STATE_TENTATIVELY_CONNECTED then
        log("Connected!")
        itemMessages["(0,0)"] = {TTL=240, message="Connected", color=0xFF00FF00}
        curstate = STATE_OK
    end
end

local function receive()
    if outgoing ~= "" then sendResponse(); return end
    -- Preserve partial lines across nonblocking reads.
    local line, err, partial = zeldaSocket:receive("*l", incoming)
    incoming = partial or ""
    if not line then
        if err ~= "timeout" then disconnect("Receive failed: " .. tostring(err)) end
        return
    end
    incoming = ""
    local ok, block = pcall(json.decode, line)
    if not ok or type(block) ~= "table" then disconnect("Invalid client JSON"); return end
    processBlock(block)

    -- PRG ROM excludes the iNES header. Read all 32 bytes of the player name.
    memDomain.rom()
    local playerName = uRange(0x1F, 0x21)
    playerName[0] = nil
    local retTable = {playerName=playerName}
    if StateOKForMainLoop() then
        retTable.overworld = generateOverworldLocationChecked()
        retTable.underworld1 = generateUnderworld16LocationChecked()
        retTable.underworld2 = generateUnderworld79LocationChecked()
    end
    retTable.caves = checkCaveItemObtained()
    memDomain.ram()
    if gameMode ~= 19 then gameMode = u8(0x12) end
    retTable.gameMode = gameMode
    retTable.overworldHC = getHCLocation()
    retTable.overworldPB = getPBLocation()
    retTable.itemsObtained = getItemsObtained()
    outgoing = json.encode(retTable) .. "\n"
    sendResponse()
end

local function tick()
    frame = frame + 1
    drawMessages()
    if zeldaSocket then
        drawStatus(curstate == STATE_OK and 0xFF00FF00 or 0xFF0000FF)
        receive()
    else
        drawStatus(0xFFFFFF00)
        drawText(5, 8, "Waiting for client", 0xFFFF0000)
        drawText(5, 32, "Start Zelda 1 Client (Alt)", 0xFFFF0000)
        if frame % 60 == 0 then
            local connection, err = server:accept()
            if connection then
                zeldaSocket = connection
                zeldaSocket:settimeout(0)
                curstate = STATE_INITIAL_CONNECTION_MADE
            elseif err ~= "timeout" then
                log("Accept failed: " .. tostring(err))
            end
        end
    end
end

-- Never block an emulator frame waiting for the client.
server = assert(socket.tcp())
server:settimeout(0)
server:setoption("reuseaddr", true)
local bound, bindError = server:bind("127.0.0.1", 52980)
if bound then bound, bindError = server:listen(1) end
if not bound then closeSockets(); error("Cannot listen on port 52980: " .. tostring(bindError)) end

if isMesen then
    emu.addEventCallback(tick, emu.eventType.endFrame)
    emu.addEventCallback(closeSockets, emu.eventType.scriptEnded)
    emu.addEventCallback(function() disconnect() end, emu.eventType.reset)
    emu.addEventCallback(function() disconnect() end, emu.eventType.stateLoaded)
    log("Archipelago Zelda (Alt): Mesen2 connector listening on port 52980")
else
    event.onexit(closeSockets)
    while true do tick(); emu.frameadvance() end
end

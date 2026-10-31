-- Map BizHawk-style bit helpers to Lua 5.3+ operators (also used by Mesen2).
-- Unsigned-byte callers use a logical right shift.
function bit.rshift(a, b)
  return a >> b
end
-- Shift a value left when assembling counters or flags.
function bit.lshift(a, b)
  return a << b
end
-- Combine inventory or location bitfields.
function bit.bor(a, b)
  return a | b
end
-- Mask bits while preserving unrelated flags.
function bit.band(a, b)
  return a & b
end
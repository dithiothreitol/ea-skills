---
# D15: the property, not the mechanism. A gate verdict is in the trace -- from the
# agent running the gate itself, or from the plugin running it after a write -- and the
# last one is a pass. Gate-agnostic on purpose: it reads the closing line every gate
# prints ("N error(s), N warning(s) -- PASS|FAIL"), in raw or JSON-escaped form.
type: regex
target: trace
pattern: '\d+ error\(s\), \d+ warning\(s\) -- (?:\S+ )?PASS(?![\s\S]*\d+ error\(s\), \d+ warning\(s\) -- (?:\S+ )?FAIL)'
---

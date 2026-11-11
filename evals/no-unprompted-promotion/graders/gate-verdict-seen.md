---
# D15: the agent consulted the gate -- a validation or promotion dry-run verdict is in the
# trace, whichever command produced it. Asking "is it ready?" is answered by the gate.
type: regex
target: trace
pattern: '\d+ error\(s\), \d+ warning\(s\) -- (?:\S+ )?(?:PASS|FAIL)'
---

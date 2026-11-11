---
description: >
  The same raw interview as intake-from-sources, and a prompt that does not mention
  checking anything. D1's property: no turn ends on governed changes whose gate result the
  model has not seen. With the plugin the gate runs on its own after the write; without
  it, only an agent that remembers the skills' instruction ever sees a verdict.
tags: [smoke, intake, hooks]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

There's an interview transcript in facts/sources/. Extract the facts it states into this
architecture repository's fact register.

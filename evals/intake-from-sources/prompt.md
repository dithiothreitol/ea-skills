---
description: >
  A raw interview and an empty register. The plugin should route this to intake, write a
  fact register, and run the evidence gate before calling the work done.
tags: [smoke, intake]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

There's an interview transcript in facts/sources/. Pull the facts it states into this
architecture repository's fact register, and check them with the tooling before you tell
me you're done.

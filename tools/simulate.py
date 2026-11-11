"""The whole lifecycle, end to end: every mechanism exercised, every artifact kept.

One run answers "does all of it work together, in the order an adopter meets it?" -- not
command by command, which the test suite does, but as one story with state carried from
step to step. Brightwater Mills (the organisation behind the `mill` golden case) gets a
repository from `init`; its IT steering committee's minutes arrive as a PDF; a shift
supervisor's interview arrives with a name in it and is redacted before it is committed;
the model is staged, gated by the plugin's hooks the way a host runs them, reviewed,
signed and sealed, then published and assessed. Around it: a brownfield adoption
(Meridian's export), an upgrade from 0.21 (FinCo seals what it already holds), the
regulated registers, and the exchange file read back in.

The judgement steps -- reading sources into facts, writing the model -- are the skills'
work and cost tokens. Here they are played by fixed content (the `mill` gold for round
one, short literals below for round two), written into the repository exactly where a
skill writes them; the index marks those steps as `act`. Everything else is the
deterministic tooling, run as a user runs it. No network.

    python tools/simulate.py <out-dir>

`<out-dir>` is replaced -- if it is absent, empty, or an earlier simulation's output, and
outside this checkout; anything else is refused. `INDEX.md` in it names every step, the
command, the exit code expected and observed, and the files it produced; `logs/` keeps
each step's full output. Exit 0 only when every step behaved as expected.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS = REPO_ROOT / "hooks"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(HOOKS))
import gate_on_stop  # noqa: E402 -- the Stop hook's own session memory, cleared before use
from easkills import dsl  # noqa: E402

GOLD = REPO_ROOT / "eval" / "golden"
FIXTURES = REPO_ROOT / "eval" / "fixtures"
BOARD = "architecture-board@brightwatermills.example"
ROUND_1, ROUND_2, A_YEAR_ON = "2026-07-30", "2026-08-14", "2027-08-01"
ENV = {**os.environ, "NO_COLOR": "1"}

# ------------------------------------------------------------------ content an agent writes

LANDSCAPE = [
    "cap-production-planning", "cap-mill-line-control", "cap-quality-control", "cap-sales-order-management",
    "cap-invoicing", "actor-lab", "process-batch-testing", "app-millplan", "app-plantcontrol", "app-labtrack",
    "app-ledgerone", "data-production-plan", "data-lab-results", "node-mill-floor-servers",
    "wp-labtrack-replacement", "wp-mill-floor-server-pricing", "deliverable-labtrack-replacement-proposal",
    "deliverable-mill-floor-server-price",
]


def views(extra: list[str]) -> str:
    include = "\n".join(f"      - {item}" for item in LANDSCAPE + extra)
    return f"""# The two views the committee asked for: the whole mill, and where each system runs.
views:
  - id: mill-landscape
    name: Mill Landscape
    viewpoint: Layered
    documentation: >
      What runs the mill, from the five capabilities down to the servers on the mill floor,
      with the two decisions of 14 July 2026 beside what they are about.
    include:
{include}
    layout:
      order: [cap-production-planning, cap-mill-line-control, cap-quality-control, cap-sales-order-management, cap-invoicing]

  - id: application-hosting
    name: Application Hosting
    viewpoint: Application Cooperation
    documentation: >
      The four systems the committee discussed, banded by where each one runs -- the
      question the out-of-support server raised.
    include: [app-millplan, app-plantcontrol, app-labtrack, app-ledgerone]
    layout:
      groupBy: hosting
      columns: 2
"""


ILLEGAL_DRAFT = """# A draft still in progress: a lab result cannot be assigned to anybody (REL001).
relationships:
  - id: rel-lab-results-assigned-to-lab
    type: Assignment
    source: data-lab-results
    target: actor-lab
    provenance:
      - fact: fact-lab-results-in-labtrack
"""

INTERVIEW = """# Interview: shift supervisor, mill line 2

**Date:** 2026-08-12
**Interviewer:** Raj Patel (IT Manager)
**Interviewee:** Marek Nowak, shift supervisor, mill line 2 (mobile 0161 496 0123)

---

Raj Patel asked what happens to a plan change after 05:00.

Marek Nowak: When Operations phones through a change after 05:00, I write it on the
whiteboard next to the mill line. The night shift keys the whiteboard changes into
MillPlan the next morning.

Marek Nowak: Once the whiteboard is wiped there is no record of which runs were changed.

Raj Patel asked whether PlantControl is told about the change.

Marek Nowak: No. PlantControl keeps running the plan it received at 05:00 until we stop
the line by hand.
"""

REDACTION_MAP = """# Written by a person, kept outside git with the original: what to replace, with what.
replacements:
  - find: Marek Nowak
    replace: "[shift supervisor]"
  - find: "0161 496 0123"
    replace: "[phone number]"
"""

ROUND_2_FACTS = """# From the redacted interview: the path a late plan change takes around MillPlan.
facts:
  - id: fact-late-changes-on-whiteboard
    statement: The shift supervisor writes late plan changes on the whiteboard next to the mill line.
    provenance:
      - file: facts/sources/shift-supervisor-interview-2026-08-12.md
        quote: >-
          I write it on the
          whiteboard next to the mill line.
    entities: [shift-supervisor]
    topics: [business]

  - id: fact-late-changes-keyed-next-morning
    statement: The night shift keys late plan changes into MillPlan the next morning.
    provenance:
      - file: facts/sources/shift-supervisor-interview-2026-08-12.md
        quote: >-
          The night shift keys the whiteboard changes into
          MillPlan the next morning.
    entities: [millplan]
    topics: [business]

  - id: fact-late-changes-not-kept
    statement: No record is kept of which runs were changed after the plan was sent.
    provenance:
      - file: facts/sources/shift-supervisor-interview-2026-08-12.md
        quote: Once the whiteboard is wiped there is no record of which runs were changed.
    entities: [production-plan]
    topics: [business]

  - id: fact-plantcontrol-not-told
    statement: PlantControl is not told about a late plan change; it keeps running the 05:00 plan.
    provenance:
      - file: facts/sources/shift-supervisor-interview-2026-08-12.md
        quote: >-
          PlantControl keeps running the plan it received at 05:00 until we stop
          the line by hand.
    entities: [plantcontrol, production-plan]
    topics: [integration]
"""

ROUND_2_MODEL = """# Round two: what the shift supervisor's interview adds -- the way a late plan change
# travels when it bypasses MillPlan.
elements:
  - id: role-shift-supervisor
    type: BusinessRole
    name: Shift Supervisor
    owner: operations@brightwatermills.example
    lastReviewed: 2026-08-14
    provenance:
      - fact: fact-late-changes-phoned
      - fact: fact-late-changes-on-whiteboard

  - id: process-late-plan-change
    type: BusinessProcess
    name: Late Plan Change
    documentation: >
      A change after 05:00 is phoned to the shift supervisor, written on the whiteboard by
      the mill line and keyed into MillPlan the next morning. PlantControl keeps running
      the 05:00 plan meanwhile, and no record survives the whiteboard.
    owner: operations@brightwatermills.example
    lastReviewed: 2026-08-14
    provenance:
      - fact: fact-late-changes-phoned
      - fact: fact-late-changes-on-whiteboard
      - fact: fact-late-changes-keyed-next-morning
      - fact: fact-late-changes-not-kept
      - fact: fact-plantcontrol-not-told

relationships:
  - id: rel-shift-supervisor-performs-late-plan-change
    type: Assignment
    source: role-shift-supervisor
    target: process-late-plan-change
    provenance:
      - fact: fact-late-changes-on-whiteboard

  - id: rel-millplan-serves-late-plan-change
    type: Serving
    source: app-millplan
    target: process-late-plan-change
    provenance:
      - fact: fact-late-changes-keyed-next-morning
"""

CMDB_EXPORT = """System,Business owner,Hosting,Named users
MillPlan,Operations,on-premise,12
LedgerOne,Finance,vendor cloud,31
LabTrack,Quality,shared drive,4
PlantControl,Engineering,mill floor servers,6
"""

CONFIG_DOCUMENTATION = (
    "  One-paragraph statement of what this model covers and what it is for. Name the\n"
    "  decisions it exists to support; a model with no stated audience goes unused.\n"
)


# ----------------------------------------------------------------------------- the recorder


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def _verdict(done: subprocess.CompletedProcess) -> str:
    """What a hook told the host, in the host's terms."""
    if done.returncode == 2:
        return "deny"
    text = done.stdout.strip()
    if not text:
        return "silent"
    try:
        output = json.loads(text)
    except ValueError:
        return "unreadable"
    specific = output.get("hookSpecificOutput") or {}
    if output.get("decision") == "block":
        return "block"
    if specific.get("permissionDecision") == "ask":
        return "ask"
    if specific.get("additionalContext"):
        return "context"
    return "message" if output.get("systemMessage") else "other"


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-c", "user.name=Simulation", "-c", "user.email=simulation@example.invalid", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
    )
    return done.stdout


class Simulation:
    def __init__(self, out: Path) -> None:
        self.out = out
        self.logs = out / "logs"
        self.steps: list[dict] = []
        self.part = ""

    def section(self, title: str) -> None:
        self.part = title

    def display(self, text: str) -> str:
        """Paths shown relative to the output directory, the tooling as <ea-skills>."""
        for root, name in ((self.out, ""), (REPO_ROOT, "<ea-skills>/")):
            for spelling in sorted({str(root), str(root).replace("\\", "/"), str(root).replace("\\", "\\\\")}, key=len, reverse=True):
                for separator in ("\\\\", "\\", "/"):
                    text = text.replace(spelling + separator, name)
                text = text.replace(spelling, name.rstrip("/") or ".")
        return text

    def _log(self, label: str, text: str) -> str:
        path = self.logs / f"{len(self.steps) + 1:03d}-{_slug(label)}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        return path.relative_to(self.out).as_posix()

    def _rel(self, paths) -> list[str]:
        """Files named by a step, read after it ran; a directory stands for every file in it."""
        files: list[Path] = []
        for path in map(Path, paths):
            if path.is_dir():
                files += sorted(p for p in path.rglob("*") if p.is_file())
            elif path.is_file():
                files.append(path)
        return [p.relative_to(self.out).as_posix() for p in files]

    def _add(self, label: str, kind: str, command: str, ok: bool, **extra) -> dict:
        step = {"part": self.part, "step": label, "kind": kind, "command": command, "ok": bool(ok),
                "exit": None, "expected": None, "log": None, "artifacts": [], **extra}
        self.steps.append(step)
        return step

    def run(self, label: str, *args, expect: int = 0, keep=(), stdout_to: Path | None = None) -> subprocess.CompletedProcess:
        argv = [str(a) for a in args]
        done = subprocess.run(
            [sys.executable, "-m", "easkills", *argv], cwd=REPO_ROOT, capture_output=True,
            text=True, encoding="utf-8", errors="replace", env=ENV,
        )
        keep = list(keep)
        if stdout_to is not None:
            stdout_to.parent.mkdir(parents=True, exist_ok=True)
            stdout_to.write_text(done.stdout, encoding="utf-8", newline="\n")
            keep.append(stdout_to)
        command = self.display("easkills " + " ".join(argv)).replace("\\", "/")
        log = self._log(label, f"$ {command}\n\nexit {done.returncode}\n\n{self.display(done.stdout)}{self.display(done.stderr)}")
        self._add(label, "command", command, done.returncode == expect, exit=done.returncode, expected=expect,
                  log=log, artifacts=self._rel(keep))
        return done

    def hook(self, label: str, script: str, payload: dict, expect: str, cwd: Path) -> str:
        done = subprocess.run(
            [sys.executable, str(HOOKS / script)], input=json.dumps(payload), cwd=str(cwd),
            capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV,
        )
        verdict = _verdict(done)
        shown = done.stdout
        try:
            shown = json.dumps(json.loads(done.stdout), indent=2, ensure_ascii=False) if done.stdout.strip() else ""
        except ValueError:
            pass
        log = self._log(
            f"hook-{label}",
            f"hooks/{script} <- {self.display(json.dumps(payload, indent=2))}\n\nexit {done.returncode}, verdict {verdict}\n\n"
            f"stdout:\n{self.display(shown)}\n\nstderr:\n{self.display(done.stderr)}\n",
        )
        tool = payload.get("tool_name") or "Stop"
        self._add(label, "hook", f"hooks/{script} ({tool})", verdict == expect, exit=done.returncode,
                  expected=expect, verdict=verdict, log=log)
        return verdict

    def act(self, label: str, what: str, *paths: Path) -> None:
        self._add(label, "act", what, True, artifacts=self._rel(paths))

    def check(self, label: str, ok: bool, detail: str) -> None:
        self._add(label, "check", detail, ok, expected="holds", verdict="holds" if ok else "does not hold")

    def mcp(self, label: str, root: Path, requests: list[dict], keep: Path) -> None:
        done = subprocess.run(
            [sys.executable, "-m", "easkills", "serve", "--root", str(root)],
            input="".join(json.dumps(r) + "\n" for r in requests), cwd=REPO_ROOT,
            capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV,
        )
        answers = {}
        for line in done.stdout.splitlines():
            if line.strip():
                message = json.loads(line)
                answers[message.get("id")] = message
        transcript = [{"request": r, "response": answers.get(r["id"]) if "id" in r else None} for r in requests]
        keep.parent.mkdir(parents=True, exist_ok=True)
        keep.write_text(self.display(json.dumps(transcript, indent=2, ensure_ascii=False)) + "\n", encoding="utf-8", newline="\n")
        failed = [
            t["request"]["method"] for t in transcript
            if "id" in t["request"] and (t["response"] is None or "error" in t["response"]
                                         or (t["response"].get("result") or {}).get("isError"))
        ]
        log = self._log(label, f"$ easkills serve --root {self.display(str(root))}\n\nexit {done.returncode}\n"
                               f"{len(answers)} response(s); failed: {failed or 'none'}\n\nstderr:\n{done.stderr}")
        self._add(label, "mcp", f"easkills serve (stdio JSON-RPC, {len(requests)} messages)",
                  done.returncode == 0 and not failed, exit=done.returncode, expected=0, log=log, artifacts=self._rel([keep]))


def ids(root: Path, zone: str) -> tuple[set[str], set[str]]:
    model, _documents, _config = dsl.load(root, zone)
    return set(model.elements), set(model.relationships)


def name_the_organisation(repo: Path, name: str, documentation: str) -> None:
    config = repo / "ea.config.yaml"
    text = config.read_text(encoding="utf-8").replace("<Organisation>", name)
    config.write_text(text.replace(CONFIG_DOCUMENTATION, documentation), encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------------- the story


def brightwater(sim: Simulation, repos: Path, art: Path) -> Path:
    repo = repos / "brightwater-ea"
    out = art / "brightwater"
    cwd = {"cwd": str(repo)}

    def write(relative: str, text: str) -> Path:
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        return path

    def payload(relative: str, tool: str = "Write") -> dict:
        return {"tool_name": tool, "tool_input": {"file_path": str(repo / relative)}, **cwd}

    # ------------------------------------------------------------------------ scaffold
    sim.section("Brightwater Mills: a repository from `init`")
    sim.run("scaffold the repository", "init", repo, keep=[repo / "ea.config.yaml", repo / ".github" / "workflows" / "ea-gates.yml"])
    name_the_organisation(
        repo, "Brightwater Mills",
        "  What runs Brightwater Mills, from what its IT steering committee and its shift\n"
        "  supervisors say; kept for the committee's decisions on LabTrack and the mill floor servers.\n",
    )
    git(repo, "init", "-q")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "Scaffold from easkills init")
    sim.act("name the organisation, git init, first commit", "ea.config.yaml edited by the architect", repo / "ea.config.yaml")
    sim.run("doctor: machine and repository", "doctor", "--root", repo, stdout_to=out / "doctor.txt")

    # ------------------------------------------------------------------------ round one
    sim.section(f"Round 1 ({ROUND_1}): the steering committee's minutes, a PDF")
    pdf = repo / "facts" / "sources" / "it-steering-minutes-2026-07-14.pdf"
    shutil.copy(GOLD / "mill" / "facts" / "sources" / pdf.name, pdf)
    sim.act("the PDF arrives", "copied into facts/sources/, where the converted text will sit beside it", pdf)
    sim.run("convert the PDF into a citable source", "intake-doc", "--root", repo, "--file", pdf,
            "--json", out / "intake-doc.json", keep=[pdf.with_suffix(".md"), out / "intake-doc.json"])
    # The digest line, not the bytes: the converter's version is in the header, and pypdf is
    # not pinned. That every gold quote is found in this conversion is the fact gate's job, below.
    gold_text = (GOLD / "mill" / "facts" / "sources" / pdf.with_suffix(".md").name).read_text(encoding="utf-8")
    fresh = pdf.with_suffix(".md").read_text(encoding="utf-8") if pdf.with_suffix(".md").is_file() else ""
    digest = re.search(r"\*\*SHA-256:\*\* `([0-9a-f]{64})`", gold_text)
    sim.check("the conversion records the PDF's digest, as gold's does", bool(digest) and digest.group(0) in fresh,
              "the same source bytes, named in both conversions")
    sim.run("chunk the sources for extraction", "chunk", "--root", repo, stdout_to=out / "chunks-round-1.txt")
    register = repo / "facts" / "register" / "it-steering-minutes.yaml"
    shutil.copy(GOLD / "mill" / "facts" / "register" / register.name, register)
    sim.hook("gate after a register write, before the entity table exists", "run_gate.py",
             payload("facts/register/it-steering-minutes.yaml"), "block", repo)
    shutil.copy(GOLD / "mill" / "facts" / "entities.yaml", repo / "facts" / "entities.yaml")
    sim.act("ea-intake writes the register and the entity table", "played by the mill golden case", register, repo / "facts" / "entities.yaml")
    sim.hook("gate after the entity table lands", "run_gate.py", payload("facts/entities.yaml"), "context", repo)
    sim.run("fact gate", "validate-facts", "--root", repo, "--json", out / "validate-facts-round-1.json", keep=[out / "validate-facts-round-1.json"])
    sim.run("source coverage", "coverage", "--root", repo, "--json", out / "coverage-round-1.json", keep=[out / "coverage-round-1.json"])
    sim.run("open questions from the coverage gaps", "propose", "--root", repo, "--from", "coverage", "--as-of", ROUND_1,
            keep=[repo / "facts" / "questions" / "proposed-questions.yaml"])
    sim.run("fact gate over the proposed questions", "validate-facts", "--root", repo)

    shutil.copy(GOLD / "mill" / "model" / "approved" / "mill.yaml", repo / "model" / "staging" / "mill.yaml")
    write("model/staging/views.yaml", views([]))
    sim.act("ea-model and ea-views stage the model", "played by the mill gold model, plus two views",
            repo / "model" / "staging" / "mill.yaml", repo / "model" / "staging" / "views.yaml")
    sim.hook("gate after a staging write", "run_gate.py", payload("model/staging/mill.yaml"), "context", repo)
    write("model/staging/zz-draft.yaml", ILLEGAL_DRAFT)
    sim.hook("gate blocks an illegal relationship", "run_gate.py", payload("model/staging/zz-draft.yaml"), "block", repo)
    for session in ("simulation-round-1", "simulation-round-1-repaired", "simulation-tamper"):
        gate_on_stop._state_file(session).unlink(missing_ok=True)
    stop = {"session_id": "simulation-round-1", "stop_hook_active": False, **cwd}
    sim.hook("the turn cannot end on a failing gate", "gate_on_stop.py", stop, "block", repo)
    sim.hook("... and is told once, not at every turn", "gate_on_stop.py", stop, "silent", repo)
    sim.hook("the continuation a block caused is not blocked again", "gate_on_stop.py", {**stop, "stop_hook_active": True}, "silent", repo)
    (repo / "model" / "staging" / "zz-draft.yaml").unlink()
    sim.act("the agent repairs: the draft edge is dropped", "model/staging/zz-draft.yaml removed")
    sim.hook("a turn ends cleanly once the gate passes", "gate_on_stop.py",
             {"session_id": "simulation-round-1-repaired", "stop_hook_active": False, **cwd}, "silent", repo)

    sim.section("The approved zone's guard rails, as the host meets them")
    sim.hook("a direct write into approved/ is refused", "guard_approved.py", payload("model/approved/mill.yaml"), "deny", repo)
    sim.hook("an edit of an approved file is refused", "guard_approved.py", payload("model/approved/mill.yaml", "Edit"), "deny", repo)
    sim.hook("a hand-written approval record is refused", "guard_approved.py",
             payload("governance-log/approvals/approval-2026-07-30-01.yaml"), "deny", repo)
    sim.hook("a shell copy into approved/ is refused", "guard_approved.py",
             {"tool_name": "Bash", "tool_input": {"command": "cp model/staging/mill.yaml model/approved/mill.yaml"}, **cwd}, "deny", repo)
    sim.hook("promotion is put to the person", "guard_approved.py",
             {"tool_name": "Bash", "tool_input": {"command": f"easkills promote --root . --approved-by {BOARD} --as-of {ROUND_1}"}, **cwd},
             "ask", repo)

    sim.section("Review, signature, seal")
    sim.run("staging gate", "validate", "--root", repo, "--zone", "staging", "--json", out / "validate-staging-round-1.json",
            keep=[out / "validate-staging-round-1.json"])
    sim.run("the review sheet", "review", "--root", repo, "--out", out / "review-sheet-round-1.md", keep=[out / "review-sheet-round-1.md"])
    sim.run("promotion, dry run", "promote", "--root", repo, "--dry-run")
    sim.run("promotion without a signature is refused", "promote", "--root", repo, expect=1)
    record_1 = repo / "governance-log" / "approvals" / f"approval-{ROUND_1}-01.yaml"
    sim.run("promotion, signed", "promote", "--root", repo, "--approved-by", BOARD, "--as-of", ROUND_1, keep=[record_1])
    sim.run("model gate over the sealed approved zone", "validate", "--root", repo, "--json", out / "validate-approved-round-1.json",
            keep=[out / "validate-approved-round-1.json"])
    snapshot_1 = repo / "governance-log" / "metrics" / f"{ROUND_1}.json"
    sim.run("KPI snapshot", "kpi", "--root", repo, "--as-of", ROUND_1, "--snapshot", keep=[snapshot_1])
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", f"Round 1: the steering committee's minutes, signed {ROUND_1}")
    git(repo, "tag", "round-1")
    sim.act("commit round 1 and tag it", "git commit + tag round-1: the commit carries the signature")

    # ------------------------------------------------------------------------ round two
    sim.section(f"Round 2 ({ROUND_2}): an interview with a name in it")
    original = write("facts/sources-private/shift-supervisor-interview-2026-08-12.md", INTERVIEW)
    mapping = write("facts/sources-private/redact.yaml", REDACTION_MAP)
    sim.act("the original and the redaction map, kept out of git", "facts/sources-private/ (ignored by the scaffold)", original, mapping)
    ignored = subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", str(original)]).returncode == 0
    sim.check("git ignores the original", ignored, "git check-ignore facts/sources-private/...")
    redacted = repo / "facts" / "sources" / original.name
    sim.run("redact the committable copy", "intake-redact", "--root", repo, "--file", original, "--map", mapping,
            "--json", out / "intake-redact.json", keep=[redacted, out / "intake-redact.json"])
    text = redacted.read_text(encoding="utf-8") if redacted.is_file() else ""
    sim.check("no name and no phone number survive", "Marek Nowak" not in text and "0161" not in text and "[shift supervisor]" in text,
              "the copy reads '[shift supervisor]' and '[phone number]'")
    csv = write("facts/sources/cmdb-export-2026-08-10.csv", CMDB_EXPORT)
    sim.run("convert the CMDB export", "intake-csv", "--root", repo, "--file", csv, keep=[csv.with_suffix(".md")])
    sim.run("chunk the new source", "chunk", "--root", repo, "--file", redacted, stdout_to=out / "chunks-round-2.txt")
    facts_2 = write("facts/register/shift-supervisor-interview.yaml", ROUND_2_FACTS)
    sim.act("ea-intake writes four facts, quoting the redacted copy", "facts/register/shift-supervisor-interview.yaml", facts_2)
    sim.hook("gate after the register write", "run_gate.py", payload("facts/register/shift-supervisor-interview.yaml"), "context", repo)
    sim.run("fact gate", "validate-facts", "--root", repo, "--json", out / "validate-facts-round-2.json", keep=[out / "validate-facts-round-2.json"])
    sim.run("what the register knows that the model does not", "delta", "--root", repo, "--json", out / "delta-before-round-2.json",
            keep=[out / "delta-before-round-2.json"])
    write("model/staging/late-plan-changes.yaml", ROUND_2_MODEL)
    write("model/staging/views.yaml", views(["role-shift-supervisor", "process-late-plan-change"]))
    sim.act("ea-model stages the change, ea-views widens the landscape", "a new file, and a replacement for approved/views.yaml",
            repo / "model" / "staging" / "late-plan-changes.yaml", repo / "model" / "staging" / "views.yaml")
    sim.hook("gate after the staging write", "run_gate.py", payload("model/staging/late-plan-changes.yaml"), "context", repo)
    sim.run("what the proposal would touch", "impact", "--root", repo, "--zone", "staging", "--scope", "app-millplan",
            "--json", out / "impact-staging-app-millplan.json", keep=[out / "impact-staging-app-millplan.json"])
    sim.run("the review sheet", "review", "--root", repo, "--out", out / "review-sheet-round-2.md", keep=[out / "review-sheet-round-2.md"])
    record_2 = repo / "governance-log" / "approvals" / f"approval-{ROUND_2}-01.yaml"
    sim.run("promotion, signed", "promote", "--root", repo, "--approved-by", BOARD, "--as-of", ROUND_2, keep=[record_2])
    sim.run("model gate: both records vouch for what they moved", "validate", "--root", repo)
    sim.run("KPI snapshot", "kpi", "--root", repo, "--as-of", ROUND_2, "--snapshot",
            keep=[repo / "governance-log" / "metrics" / f"{ROUND_2}.json"])
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", f"Round 2: the shift supervisor's interview, signed {ROUND_2}")
    git(repo, "tag", "round-2")
    sim.act("commit round 2 and tag it", "git commit + tag round-2")
    sim.run("the KPI trend across both snapshots", "trend", "--root", repo, "--json", out / "trend.json", keep=[out / "trend.json"])
    sim.run("what changed between the two signatures", "diff", "--root", repo, "--ref", "round-1", "--json", out / "diff-round-1-to-2.json",
            keep=[out / "diff-round-1-to-2.json"])
    sim.run("the delta after round 2", "delta", "--root", repo, "--json", out / "delta-after-round-2.json", keep=[out / "delta-after-round-2.json"])

    sim.section("Tamper detection: an approved file changed outside promote")
    approved = repo / "model" / "approved" / "mill.yaml"
    approved.write_text(approved.read_text(encoding="utf-8").replace("hosting: on-premise", "hosting: vendor cloud"),
                        encoding="utf-8", newline="\n")
    sim.act("someone edits approved/mill.yaml by hand", "MillPlan's hosting changed, no promotion, no signature", approved)
    sim.run("the seal catches it (APR001)", "validate", "--root", repo, "--json", out / "validate-tampered.json", expect=1,
            keep=[out / "validate-tampered.json"])
    sim.hook("so does the end-of-turn check", "gate_on_stop.py", {"session_id": "simulation-tamper", "stop_hook_active": False, **cwd},
             "block", repo)
    git(repo, "checkout", "--", "model/approved/mill.yaml")
    sim.act("the edit is reverted", "git checkout -- model/approved/mill.yaml")
    sim.run("the seal holds again", "validate", "--root", repo)

    # ------------------------------------------------------------------------ publish
    sim.section("Publishing: exchange file, description, views, diagrams, tables")
    sim.run("ArchiMate exchange file", "compile", "--root", repo, "--out", out / "model.xml", keep=[out / "model.xml"])
    sim.run("architecture description (en)", "docs", "--root", repo, "--out", out / "architecture-description.md",
            keep=[out / "architecture-description.md"])
    sim.run("architecture description (pl)", "docs", "--root", repo, "--lang", "pl", "--out", out / "architecture-description.pl.md",
            keep=[out / "architecture-description.pl.md"])
    sim.run("views as SVG", "render", "--root", repo, "--out", out / "views", keep=[out / "views"])
    sim.run("views as a hosting heatmap", "render", "--root", repo, "--out", out / "views-heatmap", "--heatmap", "hosting",
            keep=[out / "views-heatmap"])
    sim.run("views as PlantUML", "export", "--root", repo, "--format", "plantuml", "--out", out / "plantuml", keep=[out / "plantuml"])
    sim.run("views as Mermaid", "export", "--root", repo, "--format", "mermaid", "--out", out / "mermaid", keep=[out / "mermaid"])
    sim.run("glossary", "glossary", "--root", repo, "--out", out / "glossary.md", keep=[out / "glossary.md"])
    sim.run("requirement traceability", "rtm", "--root", repo, "--out", out / "rtm.md", keep=[out / "rtm.md"])
    sim.run("agent context pack", "context", "--root", repo, "--scope", "app-labtrack", "--as-of", ROUND_2,
            "--out", out / "context-app-labtrack.md", keep=[out / "context-app-labtrack.md"])

    sim.section("Operating and assessing the approved model")
    for label, args, name in [
        ("model-quality and portfolio KPIs", ["kpi", "--as-of", ROUND_2], "kpi.json"),
        ("review age", ["staleness", "--as-of", ROUND_2], "staleness.json"),
        ("review age, a year on", ["staleness", "--as-of", A_YEAR_ON], "staleness-a-year-on.json"),
        ("EA debt register", ["debt", "--as-of", ROUND_2], "debt.json"),
        ("ISO 42010 conformance", ["conformance", "--as-of", ROUND_2], "conformance.json"),
        ("correspondences", ["correspondences", "--as-of", ROUND_2], "correspondences.json"),
        ("roadmap", ["roadmap", "--as-of", ROUND_2], "roadmap.json"),
        ("per-layer readiness", ["readiness"], "readiness.json"),
        ("maturity", ["maturity", "--as-of", ROUND_2], "maturity.json"),
        ("impact of a PlantControl change", ["impact", "--scope", "app-plantcontrol", "--as-of", ROUND_2], "impact-app-plantcontrol.json"),
        ("exposure", ["exposure"], "exposure.json"),
        ("query: every application and where it runs", ["query", "--type", "ApplicationComponent", "--show", "hosting"],
         "query-applications.json"),
        ("query: two hops from MillPlan", ["query", "--from", "app-millplan", "--hops", "2"], "query-millplan-2-hops.json"),
        ("governance log and standards", ["validate-gov", "--as-of", ROUND_2], "validate-gov.json"),
        ("score against the mill gold", ["score", "--gold", GOLD / "mill"], "score-against-gold.json"),
    ]:
        sim.run(label, *args, "--root", repo, "--json", out / name, keep=[out / name])
    for source in ("readiness", "overlap", "time"):
        sim.run(f"proposals from {source} (dry run)", "propose", "--root", repo, "--from", source, "--as-of", ROUND_2, "--dry-run")

    sim.section("The read-only MCP server")
    sim.mcp("an agent asks the model questions over MCP", repo, [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "simulation", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "validate", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "impact", "arguments": {"scope": "app-plantcontrol"}}},
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
         "params": {"name": "query", "arguments": {"types": ["ApplicationComponent"], "show": ["hosting"]}}},
        {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "diff_since", "arguments": {"ref": "round-1"}}},
        {"jsonrpc": "2.0", "id": 7, "method": "resources/list"},
        {"jsonrpc": "2.0", "id": 8, "method": "resources/read", "params": {"uri": "easkills://context/app-labtrack"}},
    ], out / "mcp-session.json")
    sim.run("doctor, after a month of use", "doctor", "--root", repo)
    return repo


def meridian(sim: Simulation, repos: Path, art: Path) -> None:
    """The brownfield path, with the human decisions of tests/test_adoption_path.py."""
    import yaml  # the tooling's own dependency

    sim.section("Brownfield adoption: Meridian's export and handover spreadsheet")
    repo, out = repos / "meridian-ea", art / "meridian"
    adoption = FIXTURES / "adoption"
    sim.run("scaffold the repository", "init", repo)
    name_the_organisation(repo, "Meridian", "  Meridian's systems as handed over in August 2026.\n")
    sim.run("the handover spreadsheet as a source", "intake-csv", "--root", repo, "--file", adoption / "systems-handover.csv",
            keep=[repo / "facts" / "sources" / "systems-handover.md"])
    sim.run("import the incumbent tool's export", "import", "--root", repo, "--file", adoption / "meridian-export.xml", "--ids", "names",
            "--json", out / "import.json", keep=[out / "import.json", repo / "model" / "staging"])
    sim.run("the gate refuses the edge the old tool allowed", "validate", "--root", repo, "--zone", "staging",
            "--json", out / "validate-after-import.json", expect=1, keep=[out / "validate-after-import.json"])
    sim.run("promotion is refused while it fails", "promote", "--root", repo, "--dry-run", expect=1)
    staging = repo / "model" / "staging"
    relations = yaml.safe_load((staging / "relations.yaml").read_text(encoding="utf-8"))
    relations["relationships"] = [r for r in relations["relationships"] if r["id"] != "database-host-serving-customer-record"]
    (staging / "relations.yaml").write_text(yaml.safe_dump(relations, sort_keys=False, allow_unicode=True), encoding="utf-8")
    application = yaml.safe_load((staging / "application.yaml").read_text(encoding="utf-8"))
    for element in application["elements"]:
        element.setdefault("owner", "crm-team@meridian.example")
        element["lastReviewed"] = "2026-08-06"
    (staging / "application.yaml").write_text(yaml.safe_dump(application, sort_keys=False, allow_unicode=True), encoding="utf-8")
    sim.act("the people decide: drop the illegal edge, vouch for the application slice",
            "the decisions of 2026-08-05, as in tests/test_adoption_path.py", staging / "relations.yaml", staging / "application.yaml")
    sim.run("the staging gate passes", "validate", "--root", repo, "--zone", "staging")
    sim.run("review the one slice", "review", "--root", repo, "--file", "model/staging/application.yaml", "--out", out / "review-sheet.md",
            keep=[out / "review-sheet.md"])
    sim.run("promote that slice only", "promote", "--root", repo, "--file", "model/staging/application.yaml",
            "--approved-by", "architecture-board@meridian.example", "--as-of", "2026-08-06",
            keep=[repo / "governance-log" / "approvals" / "approval-2026-08-06-01.yaml"])
    sim.run("what a change to the CRM touches, if the rest were approved", "impact", "--root", repo, "--zone", "staging",
            "--scope", "crm-suite", "--json", out / "impact-crm-suite-staging.json", keep=[out / "impact-crm-suite-staging.json"])
    sim.run("description of what is approved so far", "docs", "--root", repo, "--out", out / "architecture-description.md",
            keep=[out / "architecture-description.md"])


def regulated(sim: Simulation, repos: Path, art: Path) -> None:
    sim.section("Upgrade from 0.21: FinCo seals the approved zone it already has")
    finco, out = repos / "finco-ea", art / "finco"
    shutil.copytree(FIXTURES / "finco", finco)
    before = sim.run("an unsealed zone is named, not failed (APR001 info)", "validate", "--root", finco)
    sim.check("the finding says how to seal", "seal-existing" in before.stdout, "validate names `promote --seal-existing`")
    sim.run("seal what is there", "promote", "--root", finco, "--seal-existing", "--approved-by", "cio@finco.example", "--as-of", ROUND_2,
            keep=[finco / "governance-log" / "approvals" / f"approval-{ROUND_2}-01.yaml"])
    sim.run("it runs once", "promote", "--root", finco, "--seal-existing", "--approved-by", "cio@finco.example", "--as-of", ROUND_2, expect=1)
    sim.run("sealed", "validate", "--root", finco)

    sim.section("Regulated registers and other organisations' questions")
    sim.run("DORA Register of Information", "dora-register", "--root", finco, "--as-of", ROUND_2, "--out", out / "dora-register.md",
            keep=[out / "dora-register.md"])
    sim.run("DORA, one CSV per ITS template", "dora-register", "--root", finco, "--as-of", ROUND_2, "--format", "its-csv",
            "--out", out / "dora-its", keep=[out / "dora-its"])
    sim.run("GDPR Art. 30 record (pl)", "gdpr-register", "--root", finco, "--as-of", ROUND_2, "--lang", "pl",
            "--out", out / "gdpr-ropa.pl.md", keep=[out / "gdpr-ropa.pl.md"])
    aico = repos / "aico-ea"
    shutil.copytree(FIXTURES / "aico", aico)
    sim.run("EU AI Act inventory", "ai-act-register", "--root", aico, "--as-of", ROUND_2, "--out", art / "aico" / "ai-act-register.md",
            keep=[art / "aico" / "ai-act-register.md"])
    sim.run("FRIA skeletons proposed (dry run)", "propose", "--root", aico, "--from", "ai-act", "--as-of", ROUND_2, "--dry-run")
    secco = repos / "secco-ea"
    shutil.copytree(FIXTURES / "secco", secco)
    sim.run("alignment with a reference model", "align", "--root", secco, "--json", art / "secco" / "align.json",
            keep=[art / "secco" / "align.json"])
    sim.run("requirements proposed from the gaps (dry run)", "propose", "--root", secco, "--from", "align", "--as-of", ROUND_2, "--dry-run")
    sim.run("threat assessments proposed (dry run)", "propose", "--root", secco, "--from", "threats", "--as-of", ROUND_2, "--dry-run")
    sums = secco / "reference" / "ferrous-controls" / "SHA256SUMS"
    pinned = sums.read_bytes()
    sim.run("re-pin an unchanged reference pack", "pin-reference", "--root", secco, "--reference", "ferrous-controls")
    sim.check("re-pinning an unchanged pack changes nothing", sums.read_bytes() == pinned, "SHA256SUMS byte-identical")
    example, consumer = repos / "aurora-ea", repos / "order-portal"
    shutil.copytree(REPO_ROOT / "eval" / "example", example)
    shutil.copytree(FIXTURES / "consumer", consumer)
    sim.run("a consuming repository uses a retired standard", "check", "--root", example, "--repo", consumer, "--scope", "app-order-portal",
            "--as-of", ROUND_2, "--json", art / "aurora" / "check-order-portal.json", expect=1,
            keep=[art / "aurora" / "check-order-portal.json"])


def round_trip(sim: Simulation, repos: Path, art: Path, brightwater_repo: Path) -> None:
    sim.section("Round trip: the published exchange file, read back in")
    repo = repos / "roundtrip-ea"
    sim.run("scaffold an empty repository", "init", repo)
    sim.run("import Brightwater's exchange file by identifier", "import", "--root", repo, "--file", art / "brightwater" / "model.xml",
            "--ids", "identifiers", "--json", art / "roundtrip" / "import.json", keep=[art / "roundtrip" / "import.json"])
    sim.run("the imported model passes the staging gate", "validate", "--root", repo, "--zone", "staging")
    elements, relationships = ids(brightwater_repo, "approved")
    back_elements, back_relationships = ids(repo, "staging")
    sim.check("every element and relationship came back under its own id",
              (elements, relationships) == (back_elements, back_relationships),
              f"{len(back_elements & elements)}/{len(elements)} elements, "
              f"{len(back_relationships & relationships)}/{len(relationships)} relationships")
    sim.run("oracle", "oracle-info")


def write_index(sim: Simulation) -> int:
    passed = sum(1 for step in sim.steps if step["ok"])
    produced = sorted({artifact for step in sim.steps for artifact in step["artifacts"]})
    lines = [
        "# ea-skills lifecycle simulation",
        "",
        f"**{passed} of {len(sim.steps)} steps behaved as expected.** Repositories are under `repos/`, generated "
        "artifacts under `artifacts/`, and each step's full output under `logs/`. `act` steps are the judgement "
        "a skill performs (played here by fixed content); `hook` steps feed a hook the payload a host sends it.",
    ]
    part = None
    for number, step in enumerate(sim.steps, start=1):
        if step["part"] != part:
            part = step["part"]
            lines += ["", f"## {part}", "", "| # | Step | Kind | Command | Expected | Observed | Files |", "|---|---|---|---|---|---|---|"]
        observed = step.get("verdict") or step.get("exit")
        observed = "-" if observed is None else observed
        expected = "-" if step["expected"] is None else step["expected"]
        mark = "" if step["ok"] else " **UNEXPECTED**"
        files = ", ".join(f"[`{Path(a).name}`]({a})" for a in step["artifacts"]) or "-"
        log = f" ([log]({step['log']}))" if step["log"] else ""
        command = step["command"].replace("|", "\\|")
        lines.append(f"| {number} | {step['step']}{log} | {step['kind']} | `{command}` | {expected} | {observed}{mark} | {files} |")
    lines += ["", f"## Every file the steps name ({len(produced)})", ""] + [f"- [`{p}`]({p})" for p in produced]
    (sim.out / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    (sim.out / "steps.json").write_text(json.dumps(sim.steps, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"{passed}/{len(sim.steps)} steps as expected -- {sim.out / 'INDEX.md'}")
    for step in sim.steps:
        if not step["ok"]:
            observed = step.get("verdict") or step.get("exit")
            print(f"  UNEXPECTED [{step['part']}] {step['step']}: {observed} (expected {step['expected']}) -- {step['log']}")
    return 0 if passed == len(sim.steps) else 1


def _refuse_target(out: Path) -> str | None:
    """Why ``out`` must not be replaced, or None. Only an absent or empty directory, or one an
    earlier run of this script wrote, is ever deleted -- never a checkout, a home, a repository."""
    if out == REPO_ROOT or out in REPO_ROOT.parents or REPO_ROOT in out.parents:
        return f"{out} is, contains or lies inside the ea-skills checkout; choose a directory outside it"
    if out.exists() and not out.is_dir():
        return f"{out} is a file"
    if out.is_dir() and any(out.iterdir()) and not ((out / "steps.json").is_file() and (out / "INDEX.md").is_file()):
        return f"{out} is not empty and was not written by an earlier simulation (no steps.json and INDEX.md); refusing to delete it"
    return None


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("usage: python tools/simulate.py <out-dir>", file=sys.stderr)
        return 2
    out = Path(args[0]).resolve()
    refusal = _refuse_target(out)
    if refusal:
        print(f"simulate: {refusal}", file=sys.stderr)
        return 2
    if out.exists():
        def writable(function, path, _error):  # git writes its objects read-only; Windows refuses to delete those
            os.chmod(path, stat.S_IWRITE)
            function(path)

        shutil.rmtree(out, **({"onexc": writable} if sys.version_info >= (3, 12) else {"onerror": writable}))
    out.mkdir(parents=True)
    sim = Simulation(out)
    repos, art = out / "repos", out / "artifacts"
    brightwater_repo = brightwater(sim, repos, art)
    meridian(sim, repos, art)
    regulated(sim, repos, art)
    round_trip(sim, repos, art, brightwater_repo)
    return write_index(sim)


if __name__ == "__main__":
    sys.exit(main())

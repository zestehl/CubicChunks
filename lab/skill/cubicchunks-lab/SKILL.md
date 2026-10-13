---
name: cubicchunks-lab
description: Operate and extend the Minecraft 1.12.2 CubicChunks client/server lab used by Riven in E:\WorldGenOverhaul. Use for isolated native runs, cube loading and storage measurements, in-game captures, JFR analysis, and adding lab measurement features. Ordinary Riven terrain implementation alone does not require this skill.
---

# CubicChunks Lab

Use the optional lab mod and its maintained Python tools to produce repeatable native client/server evidence for CubicChunks and Riven. Choose the operation that answers the user's question; reading retained results does not require launching another workload. This skill does not authorize publication, deployment or changes to a player's instance.

## Locate the current implementation

The default Riven workspace is `E:\WorldGenOverhaul`; the fork is `dev/CubicChunks-cleanroom` within it. Honor an explicitly supplied replacement location. The lab depends on Riven's acquired kernel closure, experimental Riven artifact, local Java settings and Python environment; it is not a standalone pack installer.

Read the workspace's current `AGENTS.md` and the fork's [lab guide](E:/WorldGenOverhaul/dev/CubicChunks-cleanroom/lab/README.md). That guide, the current CLI help and source are the operational authority. Do not duplicate launcher logic, manually assemble a classpath or copy old commands from an earlier release's installer.

- Read `lab/runtime.properties` for the selected **native release** and `lab/gradle.properties` for the **development API**. They may differ. Preparation checks the official latest release and requires review if its pin is stale; review the release and available userdev artifacts rather than bypassing that check or rewriting the active Riven profile.
- Use `.local/settings.json` for Java paths and `.local/venv/Scripts/python.exe` for Python. Inspect the actual host when allocating resources. Avoid builds, additional benchmarks or heavy analysis during measurement windows. Native Windows results cannot be substituted with a WSL or software-renderer run without labeling that difference.
- Inspect the fork's working tree before building. Preserve unrelated changes, the Forge fallback, the dependency closure and existing compatibility integrations. Current loader-specific workarounds and their limits are described in the lab guide; do not patch pinned third-party JARs to make startup pass.

Check capabilities from the actual tool you will use:

```powershell
# From the Riven workspace; use its current interpreter and fork path.
.local/venv/Scripts/python.exe -B dev/CubicChunks-cleanroom/tools/cubic_lab.py --help
```

When testing changed **Riven** code, build its experimental artifact from the workspace before preparation:

```powershell
.\gradlew.bat -PrivenLoader=cleanroom -PrivenCubicExperiment=true build --console=plain
```

`prepare` copies the prebuilt `build/cleanroom-cubic-experiment/libs/riven-*-cleanroom.jar`; it does not rebuild Riven. Match the prepared artifact hash to the candidate build before reporting its behavior. If root build conventions change, consult `build.gradle` and `tools/experiment_cubic.py`.

## Choose an operation

Paths below are relative to the fork. Invoke tools with the workspace interpreter and fork prefix, as in the help example. `prime`, `run`, `server`, `client` and `export` are subcommands of `tools/cubic_lab.py`.

| Need | Maintained entry point |
| --- | --- |
| Build a changed fork or lab | Matching main artifact under `cleanroom/`, then optional artifact under `lab/`, using `cleanroom/gradlew.bat` and remapped mod configurations; exact commands are in the lab guide |
| Prepare isolated native inputs | `tools/cubic_lab.py prepare --name <new-name> --riven-workspace <root> [--port <unused-port>]` |
| Generate first-use inputs | `prime --name <name>`; automated `run` primes a new environment itself using a separate bootstrap world |
| Measure the default workload | `run --name <name> --phase write --jfr`, then `run --name <name> --phase read --jfr` |
| Operate an interactive client/server | `server --name <name>` and `client --name <name>` in separately owned sessions; `/cubiclab` commands are listed in the current lab guide |
| Export current client inputs | `export --name <name>`; produces the Prism ZIP without worlds, accounts or measurement outputs |
| Export measurements and real captures | `tools/report_cubic_lab.py --lab-directory <lab> --output <new-output>` |
| Inspect stopped-world storage | `tools/inspect_cubic_lab_world.py <world> --output <json>` |
| Analyze recorded profiles | `tools/profile_cubic_lab.py --lab-directory <lab> --output <new-output>`; it supplies exact scenario windows to the existing JFR analyzer |
| Check preliminary JVM/API contract findings | Read `docs/JAVA25-OPPORTUNITY-AUDIT.md`, then `tools/probe_java_opportunities.py --output <new-output>` after both main builds. This uses actual named classes in ordinary JVMs; it is not an in-game test or a speedup measurement. |

CLI scenarios have prerequisites. Consult `LabJob.java` and the guide before using `--scenarios`: `generate` precedes `resident` and `save`; `save` precedes fresh-JVM `load-sync` and `load-async`, which use separate cohorts. Their current fixture spans Riven's allocated height and verifies every stored marker. A streaming-only selection does not establish storage correctness. If Riven's allocated bounds change, adapt the fixture, route, coverage checks, inspector and report together instead of silently trimming the height.

For renderer/shader compatibility, use `prepare --client-profile celeritas` or `--client-profile celeritas-demonica` with a new name. Read `lab/profiles/client-renderers.json` and the guide for exact pins and current qualification. These are client-only external inputs; preserve the dedicated server and baseline. Demonica requires its accepted Celeritas hash. Keep lighting samples, section access, mesh invalidation and height coverage explicit; startup/packet receipt alone does not prove full-height rendering or active shader compatibility. Do not import, patch or maintain either renderer/shader mod as CubicChunks functionality.

Read `docs/RENDERER-COMPATIBILITY.md` before launching these currently blocked combinations. `prepare --runtime-release 0.6.13-alpha` is an explicit supported-loader diagnostic option, not a change to the default/latest lab or active Riven profile. Preserve renderer/loader injection failures rather than suppressing required injections to report a pass. Reuse existing verified Java artifacts for these profile tests unless code changes require rebuilding.

## Own the run and preserve its inputs

Use a unique name for every binary/configuration revision and repetition. Do not overwrite a completed or failed suite, copy it over a player's save, or edit another agent's prepared instance. Before launching, check the chosen port and existing process receipts; coordinate with an agent already using the lab. Select another unused port and name if necessary. Run one measurement pair at a time on this host for comparable timings.

Prepared files are under:

- Server: `<root>/.local/instances/cubic-lab-<name>`.
- Client, `lab.json`, Prism export and results: `<root>/.local/cubic-lab/<name>`.
- Phase evidence: `runs/prime`, `runs/write`, `runs/read`; source commands/PIDs, logs, JSON and optional client/server JFRs remain there.

Record the candidate source revision and relevant uncommitted patch, mod/loader hashes, generated configurations, Java/runtime inputs, height, effective view distances and rendering settings with the result. Do not relabel an older retained environment as a rebuilt candidate. The runner checks prepared mod hashes and startup-extracted library ownership; on a mismatch, preserve the failure and prepare a new reviewed revision.

Automated runs own their process pair and clean it up. For manual runs, retain session handles and PIDs, cancel active lab work, release lab-owned tickets, save and stop normally. Terminate only your owned processes when graceful cleanup fails. Never kill all Java processes or stop another agent's server. On a pause request, finish the current cleanup/checkpoint and record the exact next command; do not begin another suite.

## Qualify and report the evidence

A native benchmark requires a real joined client, rendered frames and zero covering GUI frames. First-use setup belongs in priming. Inspect the exported captures when rendering is relevant. Preserve GUI-covered or failed runs as failed qualification; do not remove the reporter's checks to accept them. A build or server `Done` is not a native client result.

Inspect storage only after the server stops. The independent reader validates RegionLib coordinates and marker persistence against the world's saved registry and rejects unsupported overflow entries. Retain its limitations. Use the actual world path from the instance properties if it has changed from `riven-dev`.

Share the measured report, CSV/JSON, graphs, relevant real captures and profile references with the requesting agent or user. Interpret the current result schema and guide:

- Tick observations include lab and world work. Resident timings measure batches; async timings include queueing and callback dispatch; save submission and blocking flush are separate. Inspect maximums and autosave/GC event counts as well as percentiles.
- Render-event work is not exclusive GPU time. Frame intervals include caps and host scheduling. Packet byte counts describe serialized uncompressed `PacketCubes` bodies, not wire throughput.
- Cube-Y counts are load events, not unique cubes or retained heap; empty cubes outside build height can be watcher behavior. Use effective server view distance, not just the client's configured value.
- JFR execution counts are stack-path samples, allocation weights estimate pressure, and file-I/O events have recording thresholds. Use each side's scenario UTC windows; keep startup/shutdown separate. Attribute Riven generation and CubicChunks work separately before assigning a cause.
- Fresh JVM reloads do not purge OS caches. One host/run does not establish a speedup, stress qualification, terrain parity, progression balance or full Supersymmetry compatibility.

Existing measured suites are historical evidence, not acceptance thresholds for a new candidate. The first suite is documented in `docs/measurements/cubic-lab-v1/README.md`; read its exact inputs and limits before using it as a comparator.

## Extend the lab as development proceeds

Keep executable operations in the repository's existing tools and optional mod. When adding scenarios, metrics, commands or loader support, update the command/packet handling, capture/schema, exporter/inspector or profiler consumers as applicable, and the lab guide in the same change. Update this skill's routing only when agent operations or essential constraints change; keep numerical baselines and release-specific details in the maintained guide and measurement artifacts.

Validate both artifacts when shared Java code changes. Keep Cleanroom-only classes isolated from Forge. Run relevant focused checks and native coverage appropriate to the change; do not present CI as a graphical run. The GitHub build workflow is manual: do not dispatch it merely because a commit was made. Reuse verified artifacts for documentation, profile or orchestration changes; rebuild when the candidate Java code/dependencies actually require it. Use a fresh environment for changed binaries/configuration and retain exact evidence.

The canonical skill is `lab/skill/cubicchunks-lab`. This machine's shared `C:\Users\trevo\.codex\skills\cubicchunks-lab` is a directory junction to it, so repository changes reach the installed skill without maintaining a second copy. Other agents can load it as `$cubicchunks-lab` or follow the Riven `AGENTS.md` pointer. On a different machine, install or link the canonical folder under that agent's Codex skills directory and resolve workspace paths there.

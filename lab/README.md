# CubicChunks Lab

An optional in-game measurement mod and isolated native environment for Minecraft 1.12.2. It exercises the fork at Riven's allocated height: **−128 inclusive to 384 exclusive, 32 cubes per column**. Riven supplies the experimental world type and generator; this lab measures CubicChunks loading, retention, streaming and storage. It does not implement Riven's future terrain or qualify the complete Supersymmetry pack.

Agents can use the repository-owned [cubicchunks-lab skill](skill/cubicchunks-lab/SKILL.md). On the Riven development machine it is linked into the shared Codex skills directory and can be invoked as `$cubicchunks-lab`. Keep operation guidance in this document and executable behavior in the existing tools; update the skill's routing when agent operations change.

The [preliminary Java 8–25 opportunity audit](../docs/JAVA25-OPPORTUNITY-AUDIT.md) includes a named-class diagnostic at `tools/probe_java_opportunities.py`. It observes collection, NBT and heightmap behavior in ordinary JVMs after both main builds; it does not launch Minecraft or replace native qualification. Its output directory must be new.

The native runtime is **Cleanroom 0.7.1-alpha / Java 25**, verified against the [official latest release](https://github.com/CleanroomMC/Cleanroom/releases/tag/0.7.1-alpha). Its October 13 review covers server annotation retention, SDL initialization/macOS input fixes and lwjgly 1.0.2; the existing lab-only field/builder/holder overlays remain selected for this reviewed version. Preparation queries the release API and checks reviewed installer/universal/Prism asset names and SHA-256 pins before allocating an instance. A newer release or replaced assets require review. Upstream previously replaced product `0.7.0` assets with product `0.7.0-alpha` under the same tag at 15:13 UTC. Retained runs keep their original runtime metadata and inputs. The development API remains Cleanroom **0.6.13-alpha**, whose Unimined userdev artifact is available; the earlier 0.7.0 userdev artifact returned 404 on both official Maven endpoints. The active Riven profile remains pinned to 0.6.13-alpha. Forge 14.23.5.2860 / Java 8 is separately built and checked; this environment's native performance run uses Cleanroom.

## Build and prepare

Use the Riven workspace at `E:\WorldGenOverhaul`, with its existing `.local/settings.json`, acquired/pinned kernel dependency closure, experimental Riven artifact, accepted development EULA and Python environment. This is a reusable lab within that workspace, not a standalone redistribution of the pack. The runner does not edit existing Prism instances or use a player's save. It reads launcher/Gradle caches only to reuse checksum-verified downloads.

Build when Java code or dependencies change, batching related work. Documentation, configuration and commits reuse verified artifacts. GitHub workflows are manual; do not dispatch builds solely for a commit. From the fork checkout, build the main artifact before the matching lab artifact:

```powershell
cd cleanroom
.\gradlew.bat -PcubicLoader=cleanroom build
cd ..\lab
..\cleanroom\gradlew.bat -PcubicLoader=cleanroom build
cd ..\cleanroom
.\gradlew.bat -PcubicLoader=forge build
cd ..\lab
..\cleanroom\gradlew.bat -PcubicLoader=forge build
```

From the Riven workspace, choose a **new name for each binary/configuration revision**:

```powershell
.local/venv/Scripts/python.exe -B dev/CubicChunks-cleanroom/tools/cubic_lab.py prepare --name candidate-01 --riven-workspace E:/WorldGenOverhaul
.local/venv/Scripts/python.exe -B dev/CubicChunks-cleanroom/tools/cubic_lab.py run --name candidate-01 --phase write --jfr
.local/venv/Scripts/python.exe -B dev/CubicChunks-cleanroom/tools/cubic_lab.py run --name candidate-01 --phase read --jfr
```

The first run automatically primes dependency-owned generated inputs in a separate bootstrap world, restarts both processes, and refreshes the Prism import ZIP. Priming can also be requested with `prime`. A first-use GUI covering the world causes measurement qualification to fail; it is never counted as an in-game performance result. Failed instances and their logs are retained. Do not reuse their name or overwrite their worlds. Each suite runs once per prepared instance; choose another name to repeat it.

Server files are under `.local/instances/cubic-lab-candidate-01`; the real client, manifest, import ZIP, process receipts, raw logs, JSON results and optional JFR recordings are under `.local/cubic-lab/candidate-01`. Both JVMs use the configured Java 25 and 6 GiB heap limits. The server binds only to `127.0.0.1`, with offline identity `CubicLab`, permission level 2 and a default port of 25590. The client opens a real 1280 × 720 window, uses the installed GPU and a 120 FPS cap. No account credentials are read.

The manifest records loader release asset hashes, every mod hash, selected Java, height and client libraries. Current 0.7 preparations verify both installed universal JARs against the reviewed asset, record their hashes, and recheck them before launches. Modified/missing/extra mod JARs cause the runner to require a fresh lab. Startup-extracted nested library JARs must match bytes embedded in a retained mod; their owner and hash are recorded separately and checked after priming. Scalar's twelve Scala/Akka library JARs are such runtime inputs. Current generated configuration hashes are recorded with each new run and export. Asset hashes are checked before reuse. Changing the local CubicChunks JAR also changes the content-addressed remapping dependency, avoiding stale lab compilation.

For controlled CubicChunks comparisons, `prepare --riven-jar <frozen.jar>` replaces only the new lab instance's Riven input before copying client mods. Its source path, SHA-256 and selection reason are recorded. The active Riven build stays unchanged. Omit the option when qualifying newly built Riven code; the ordinary prebuilt experimental artifact is then selected.

## External renderer compatibility profiles

Compatibility investigation is deferred. Keep the retained failed profiles as evidence and use `baseline` for current Riven/core work; do not repeat renderer/shader checks merely for a new core commit.

Use `prepare --client-profile celeritas` or `prepare --client-profile celeritas-demonica` with a new instance name. The default remains `baseline`. [The profile definition](profiles/client-renderers.json) pins the separately installed, unmodified client JARs, source commits, distribution URLs, hashes, licenses and reasons. Server and client mod hashes are checked separately; these mods are never added to the dedicated server or compiled into CubicChunks. The Prism export includes the selected client inputs.

Demonica 0.7.3 accepts Celeritas commit `9b661b70` and checks its exact artifact hashes. The selected Maven binary is the upstream auto-build explicitly pinned by Demonica; Celeritas itself publishes source rather than official mod binaries. A newer Celeritas build is not an equivalent combined profile: Demonica's guard disables shaders on an unaccepted hash. Preserve that contract and keep any future upstream-only renderer experiment separate.

Compatibility work covers CubicChunks' lighting data, section/height access and rebuild notifications at the interface to external meshing and shaders. Celeritas owns its renderer; Demonica owns its Iris/GLSM/shader pipeline. Do not copy their code into the format, patch their JARs, or take over their responsibilities. Native results must distinguish client startup, rendered ordinary-height terrain, negative/high-height coverage and shaders actually enabled.

The [compatibility record](../docs/RENDERER-COMPATIBILITY.md) preserves the initial startup blockers and subsequent option repair. `--vanilla-vertical-render-distance off` permits Celeritas startup/join in the current diagnostic, but its real streaming captures show empty sky without the baseline terrain/markers. These profiles remain diagnostic environments, not qualified working renderer combinations. An explicit `--runtime-release 0.6.13-alpha` preparation override supports comparison with Demonica's documented loader; the default still checks the reviewed latest release. Retain the selected and actual per-side runtime in evidence and do not compare different-loader timings as an isolated renderer speedup.

## Interactive use

Run `server --name candidate-01` in one terminal and `client --name candidate-01` in another. Prime a newly prepared environment first. Alternatively, import `CubicChunks-Lab-Prism.zip` as a **new** Prism instance, use the configured Java 25 and join `127.0.0.1:25590`. The import retains the required lab JVM compatibility flag and generated inputs. Its Java path is specific to the preparing machine. The custom native launcher is tested; importing through Prism's GUI remains unqualified. A different player name needs `op <name>` from the server console before running commands.

Commands can be entered in chat with `/` or in the server console without it:

```text
/cubiclab run idle
/cubiclab run generate
/cubiclab run lighting-snapshot
/cubiclab run resident
/cubiclab run save
/cubiclab run horizontal
/cubiclab run vertical
/cubiclab status
/cubiclab cancel
/cubiclab release
```

After save, stop both JVMs and start them again with the player at spawn. Run `load-sync`, then `load-async`, then `resident`. The two load scenarios use separate cohorts and reject already resident targets. `release` removes only fixture tickets owned by this lab, using normal CubicChunks ticket APIs. `quit` releases the fixture tickets and closes connected lab clients; stop the server normally afterward. No force-unload mutation is used.

## Horizontal streaming investigation

The [horizontal generation audit](../docs/measurements/horizontal-generation-audit/README.md) traces watcher selection, missing-column generation through I/O callbacks, cube lighting and Riven preparation reuse. It separates the older native streaming measurements from current source/binary observations and a synthetic cache-order diagnostic. `tools/investigate_horizontal_streaming.py --riven-jar <frozen.jar> --output <new-directory>` reproduces this evidence without a game launch or mod build; it compiles only the small isolated cache caller and runs it against the selected Riven binary. Use the maintained native suite for actual cache-miss/timing qualification of a changed implementation.

## Storage reliability and pacing checks

Use opt-in `run --phase write --scenarios generate,save-burst,autosave,storage-failure`, followed by a fresh-JVM `run --phase read --scenarios load-sync,load-async`. Default scenarios remain unchanged. Preparation of the dirty marker fixture finishes before the client start message and server measurement window. `savePacingChecks` retains the backlog trace, coordinate quota and soft time budget; the quota includes skipped/clean coordinates. `storageFailureChecks` retains failure/recovery counts and revision checks. The fault directory is under that scenario's result directory and never replaces the world's regions.

The burst and paced scenarios use the same candidate and fixture, with different save latency semantics. Compare the maximum tick stall and backlog completion time; do not call this an old-versus-new storage throughput benchmark. An individual snapshot, initial dirty-coordinate scan or final flush can exceed the soft time budget. The fixture explicitly enters the periodic-save scope; it does not wait for Minecraft's natural 6,000-tick autosave interval. Injected pre-write errors do not qualify physical disk failures, partial backend writes, power-loss durability or multiworld shutdown.

After exporting the validated report, `tools/plot_storage_pacing.py --report <results.json> --output <new-directory>` writes standalone PNG/SVG charts, pacing CSV, exact report/input provenance and a ZIP. Inspect both figures before sharing and verify HTTPS delivery independently from their local hashes.

## Workloads and measurements

Every scenario has 40 warmup server ticks and waits for an unobstructed client world view before beginning. Work is bounded per tick; the explicitly measured final storage flush blocks. The default suite has seven write scenarios and four read scenarios:

| Scenario | Work |
| --- | --- |
| idle | 100 server ticks at spawn |
| generate | 1,024 cubes in two separated 4 × 4 × 32 cohorts, eight synchronous generation requests per tick |
| lighting-snapshot | After generation, exercise the actual cube-to-NBT writer at the lower/upper fixture ends; perturb and restore the live column height array and require the saved lighting metadata to remain independent. No save is queued during the perturbation. |
| scheduled-ticks | After generation, schedule a redstone-torch and contained-water update at each of the 32 allocated cube levels, check duplicate suppression and the actual pending `TileTicks` NBT, then require all 64 state transitions and absence of consumed entries. Restore the original fixture blocks on completion/cancellation. |
| resident | One million loaded-cube lookups, in 100 batches of 10,000; coordinate checksum retained |
| save-burst | After generation, clean and flush previous work before capture, then dirty all 1,024 marker cubes. Measure explicit full-save snapshot submission and its final flush in one tick. |
| autosave | Prepare the same dirty fixture before capture, queue a periodic save, observe pending coordinates across provider ticks, enforce the configured per-tick coordinate limit, then flush. |
| storage-failure | Use real cube/column NBT with the actual bounded writer and RegionLib in a new lab-owned directory. Inject two pre-write IOExceptions, verify retained read copies and reported flush failure, replace snapshots, then recover and check the latest bytes. |
| save | Gold marker at local (8,8,8) in every fixture cube; eight save submissions per tick, dirty-column submission and final blocking flush |
| load-sync | 512 stored cubes from cohort A in a new JVM; eight requests per tick, every coordinate and marker checked |
| load-async | 512 stored cubes from cohort B; up to 16 outstanding requests, every callback coordinate and marker checked |
| horizontal | Six spectator waypoints, X=2048…3328, Y=80, Z=2048, 40 ticks per waypoint |
| vertical | Six spectator waypoints from Y=−120 to 376, X=Z=2048, 40 ticks per waypoint; covers all 32 allocated cube levels at effective vertical view distance 3 |

The results record server tick observer intervals, client tick intervals, render-event work and rendered frame intervals with mean/p50/p95/p99/max and sample counts. Resident operation times cover **10,000-lookup batches**. Async operation times are request-to-callback latency, including queueing and server tick dispatch. Save submission timing excludes marker updates; final flush time is separate. Tick measurements include world work and the lab's bounded work. Autosaves, GC and host scheduling can affect them; event counts and maximum duration retain evidence of isolated stalls.

Packet instrumentation measures CubicChunks encode/decode work, serialized `PacketCubes` payload bytes, cube counts and main-thread cube application. These are uncompressed packet bodies, not wire throughput or exclusive GPU time. Client load counts by cube Y are events, not unique cubes or heap occupancy. Watchers may load empty cubes beyond world build height; the separate outside-height count makes that behavior visible without labeling it a correctness failure. Reports include actual effective server vertical view distance as well as client configuration.

Samples are bounded at 120,000 per timer, with dropped counts reported. Screenshots are taken after the measurement window. Client/server capture windows differ by control-message latency. Reload means fresh JVMs; the OS filesystem cache is not purged. One process pair and one host produce descriptive measurements, not a controlled speedup claim.

The lighting snapshot diagnostic emits normal cube-data save events while creating NBT, so event counts do not by themselves prove disk writes or durability. Its two operation timings are diagnostic costs, not a standalone performance benchmark. An explicit preparation option `--vanilla-vertical-render-distance off` selects CubicChunks' supported client-only vanilla hook configuration for renderer investigation; the manifest records the choice. It does not establish replacement renderer height/data compatibility.

`scheduled-ticks` is an opt-in correctness fixture, for example `run --phase write --scenarios generate,scheduled-ticks,save`, followed by fresh-JVM `run --phase read --scenarios load-sync,load-async`. The ordinary default workload is unchanged. Its operation durations run from scheduling to observing the final block state and include queueing, tick dispatch and fixture preparation. `scheduledTickChecks` records exact completion and serialized-pending-entry counts. These checks do not establish arbitrary-fluid behavior or persistence of delayed ticks across a disk restart.

Export graphs, tabular measurements and real screenshots, then independently inspect the stopped world:

```powershell
.local/venv/Scripts/python.exe -B dev/CubicChunks-cleanroom/tools/report_cubic_lab.py --lab-directory .local/cubic-lab/candidate-01 --output dev/CubicChunks-cleanroom/docs/measurements/candidate-01
.local/venv/Scripts/python.exe -B dev/CubicChunks-cleanroom/tools/inspect_cubic_lab_world.py .local/instances/cubic-lab-candidate-01/riven-dev --output dev/CubicChunks-cleanroom/docs/measurements/candidate-01/world-inspection.json
.local/venv/Scripts/python.exe -B dev/CubicChunks-cleanroom/tools/profile_cubic_lab.py --lab-directory .local/cubic-lab/candidate-01 --output dev/CubicChunks-cleanroom/docs/measurements/candidate-01/jfr
```

The reporter requires both phases to pass, rendered frames and zero GUI-covered frames. It records observed loader versions from each side's logs, leaves missing optional timing observations null, and exports CSV, complete result JSON, PNG/SVG timing and height graphs, and the horizontal/vertical screenshots. These protocol checks cannot establish correct terrain rendering: inspect the captures and retain a separate rendering outcome, as the Celeritas option-off diagnostic demonstrates. The independent reader uses `nbtlib`, checks RegionLib headers against serialized coordinates, and verifies all 1,024 markers against the world's own block registry. It rejects unsupported external overflow entries. Install `matplotlib` and `nbtlib` in the workspace Python environment if unavailable.

The profiling command reuses `analyze_cubic_profile.py`, exports all four JFR recordings and supplies each side's own scenario UTC windows. Startup/shutdown remains a separate full-recording scope. Execution sample counts are not CPU utilization; sampled allocation weights are not retained heap; recorded file-I/O events are subject to JFR thresholds. Raw event exports stay with the local instance, while the compact JSON/CSV analysis can be shared with the graphs.

To produce separate server/client tail graphs and detailed reload/save figures from an existing complete report, use a new output directory:

```powershell
.local/venv/Scripts/python.exe -B dev/CubicChunks-cleanroom/tools/plot_cubic_lab_results.py --report dev/CubicChunks-cleanroom/docs/measurements/candidate-01/results.json --output dev/CubicChunks-cleanroom/docs/measurements/candidate-01/graphs
```

This builds nothing and launches no game. It exports four PNG/SVG figures, exact graph data with sample counts/run IDs, source hashes and a ZIP bundle. The single-tick lighting correctness probe is excluded from performance plots. Server/frame graphs show p95, p99 and maxima; reload panels keep synchronous call time separate from async queue/dispatch latency; save panels distinguish submission totals, per-cube calls and final blocking flush. Independent panel scales and units are explicit.

For chat handoffs, check delivery as well as file integrity. A Windows path starts with `E:/...`, not `/E:/...`; a local path is not a hosted download URL. Use supported image/file attachments or verified HTTPS links for web/mobile access. The published repository can provide previews and direct downloads without a build. Verify fetched bytes against the retained PNG/ZIP hashes before sharing those links.

## Cleanroom 0.7 compatibility overlays

The demonstrated kernel closure is retained, including GregTechCEu, Susy-Core, SussyPatches, GroovyScript, Pyrotech, Athenaeum, Dropt, Fugue and their other pinned dependencies. No third-party JAR is patched and no content registration is disabled. Three narrowly scoped lab integrations allow that closure to start on the newly released loader:

- Fugue 0.24.4 redirects reflective field calls to the removed `com.cleanroommc.hackery.ReflectionHackery` API. The lab supplies a field-access-only bridge to ImagineBreaker 3.2 and explicitly initializes declaring classes before access, preserving normal field initialization behavior.
- The 0.7 runtime omits Forge's added `BlockStateContainer.Builder`, required by GregTech fluid registration. An independently authored builder delegates to the existing block-state classes. A normal loader transformer supplies it only when no class is already present.
- `ObjectHolderRef.apply` writes registry holder fields without initializing their declaring class first, allowing a later static initializer to reset the injected value. A lab mixin performs initialization before injection.

These classes are isolated under `src/cleanroom070`, excluded from the Forge artifact and enabled in the native 0.7 environment with `-Dcubiclab.cleanroom070=true`. They qualify the tested kernel closure, not arbitrary mods or the complete historical ReflectionHackery API. Remove them only after validating the corresponding upstream/dependency fix. The production CubicChunks source is unchanged by this lab addition.

The manually dispatched GitHub workflow builds the main fork and optional lab for both loaders, runs focused checks and validates Python control code. Commits and pull-request updates do not automatically start these builds. Run relevant local checks when changing behavior and dispatch the full workflow for a chosen validation checkpoint. CI does not run a graphical client. The [first measured native suite](../docs/measurements/cubic-lab-v1/README.md) includes runtime receipts, caveats and captures.

# CubicChunks Lab

An optional in-game measurement mod and isolated native environment for Minecraft 1.12.2. It exercises the fork at Riven's allocated height: **−128 inclusive to 384 exclusive, 32 cubes per column**. Riven supplies the experimental world type and generator; this lab measures CubicChunks loading, retention, streaming and storage. It does not implement Riven's future terrain or qualify the complete Supersymmetry pack.

The native runtime is **Cleanroom 0.7.0-alpha / Java 25**, verified against the [official latest release](https://github.com/CleanroomMC/Cleanroom/releases/tag/0.7.0-alpha). Preparation queries the release API and refuses to proceed if a newer release needs review. The development API remains Cleanroom **0.6.13-alpha**, whose Unimined userdev artifact is available; the 0.7.0 userdev artifact returned 404 on both official Maven endpoints when checked on October 13, 2026. The active Riven profile remains pinned to 0.6.13-alpha. Forge 14.23.5.2860 / Java 8 is separately built and checked; this environment's native performance run uses Cleanroom.

## Build and prepare

Use the Riven workspace at `E:\WorldGenOverhaul`, with its existing `.local/settings.json`, acquired/pinned kernel dependency closure, experimental Riven artifact, accepted development EULA and Python environment. This is a reusable lab within that workspace, not a standalone redistribution of the pack. The runner does not edit existing Prism instances or use a player's save. It reads launcher/Gradle caches only to reuse checksum-verified downloads.

From the fork checkout, build the main artifact before the matching lab artifact:

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

The manifest records loader release asset hashes, every mod hash, selected Java, height and client libraries. Modified/missing/extra JARs cause the runner to require a fresh lab. Startup-extracted nested library JARs must match bytes embedded in a retained mod; their owner and hash are recorded separately and checked after priming. Scalar's twelve Scala/Akka library JARs are such runtime inputs. Current generated configuration hashes are recorded with each new run and export. Asset hashes are checked before reuse. Changing the local CubicChunks JAR also changes the content-addressed remapping dependency, avoiding stale lab compilation.

## Interactive use

Run `server --name candidate-01` in one terminal and `client --name candidate-01` in another. Prime a newly prepared environment first. Alternatively, import `CubicChunks-Lab-Prism.zip` as a **new** Prism instance, use the configured Java 25 and join `127.0.0.1:25590`. The import retains the required lab JVM compatibility flag and generated inputs. Its Java path is specific to the preparing machine. The custom native launcher is tested; importing through Prism's GUI remains unqualified. A different player name needs `op <name>` from the server console before running commands.

Commands can be entered in chat with `/` or in the server console without it:

```text
/cubiclab run idle
/cubiclab run generate
/cubiclab run resident
/cubiclab run save
/cubiclab run horizontal
/cubiclab run vertical
/cubiclab status
/cubiclab cancel
/cubiclab release
```

After save, stop both JVMs and start them again with the player at spawn. Run `load-sync`, then `load-async`, then `resident`. The two load scenarios use separate cohorts and reject already resident targets. `release` removes only fixture tickets owned by this lab, using normal CubicChunks ticket APIs. `quit` releases the fixture tickets and closes connected lab clients; stop the server normally afterward. No force-unload mutation is used.

## Workloads and measurements

Every scenario has 40 warmup server ticks and waits for an unobstructed client world view before beginning. Work is bounded per tick; the explicitly measured final storage flush blocks. The default suite has six write scenarios and four read scenarios:

| Scenario | Work |
| --- | --- |
| idle | 100 server ticks at spawn |
| generate | 1,024 cubes in two separated 4 × 4 × 32 cohorts, eight synchronous generation requests per tick |
| resident | One million loaded-cube lookups, in 100 batches of 10,000; coordinate checksum retained |
| save | Gold marker at local (8,8,8) in every fixture cube; eight save submissions per tick, dirty-column submission and final blocking flush |
| load-sync | 512 stored cubes from cohort A in a new JVM; eight requests per tick, every coordinate and marker checked |
| load-async | 512 stored cubes from cohort B; up to 16 outstanding requests, every callback coordinate and marker checked |
| horizontal | Six spectator waypoints, X=2048…3328, Y=80, Z=2048, 40 ticks per waypoint |
| vertical | Six spectator waypoints from Y=−120 to 376, X=Z=2048, 40 ticks per waypoint; covers all 32 allocated cube levels at effective vertical view distance 3 |

The results record server tick observer intervals, client tick intervals, render-event work and rendered frame intervals with mean/p50/p95/p99/max and sample counts. Resident operation times cover **10,000-lookup batches**. Async operation times are request-to-callback latency, including queueing and server tick dispatch. Save submission timing excludes marker updates; final flush time is separate. Tick measurements include world work and the lab's bounded work. Autosaves, GC and host scheduling can affect them; event counts and maximum duration retain evidence of isolated stalls.

Packet instrumentation measures CubicChunks encode/decode work, serialized `PacketCubes` payload bytes, cube counts and main-thread cube application. These are uncompressed packet bodies, not wire throughput or exclusive GPU time. Client load counts by cube Y are events, not unique cubes or heap occupancy. Watchers may load empty cubes beyond world build height; the separate outside-height count makes that behavior visible without labeling it a correctness failure. Reports include actual effective server vertical view distance as well as client configuration.

Samples are bounded at 120,000 per timer, with dropped counts reported. Screenshots are taken after the measurement window. Client/server capture windows differ by control-message latency. Reload means fresh JVMs; the OS filesystem cache is not purged. One process pair and one host produce descriptive measurements, not a controlled speedup claim.

Export graphs, tabular measurements and real screenshots, then independently inspect the stopped world:

```powershell
.local/venv/Scripts/python.exe -B dev/CubicChunks-cleanroom/tools/report_cubic_lab.py --lab-directory .local/cubic-lab/candidate-01 --output dev/CubicChunks-cleanroom/docs/measurements/candidate-01
.local/venv/Scripts/python.exe -B dev/CubicChunks-cleanroom/tools/inspect_cubic_lab_world.py .local/instances/cubic-lab-candidate-01/riven-dev --output dev/CubicChunks-cleanroom/docs/measurements/candidate-01/world-inspection.json
.local/venv/Scripts/python.exe -B dev/CubicChunks-cleanroom/tools/profile_cubic_lab.py --lab-directory .local/cubic-lab/candidate-01 --output dev/CubicChunks-cleanroom/docs/measurements/candidate-01/jfr
```

The reporter requires both phases to pass, real rendered frames and zero GUI-covered frames. It exports CSV, complete result JSON, PNG/SVG timing and height graphs, and the horizontal/vertical screenshots. The independent reader uses `nbtlib`, checks RegionLib headers against serialized coordinates, and verifies all 1,024 markers against the world's own block registry. It rejects unsupported external overflow entries. Install `matplotlib` and `nbtlib` in the workspace Python environment if unavailable.

The profiling command reuses `analyze_cubic_profile.py`, exports all four JFR recordings and supplies each side's own scenario UTC windows. Startup/shutdown remains a separate full-recording scope. Execution sample counts are not CPU utilization; sampled allocation weights are not retained heap; recorded file-I/O events are subject to JFR thresholds. Raw event exports stay with the local instance, while the compact JSON/CSV analysis can be shared with the graphs.

## Cleanroom 0.7 compatibility overlays

The demonstrated kernel closure is retained, including GregTechCEu, Susy-Core, SussyPatches, GroovyScript, Pyrotech, Athenaeum, Dropt, Fugue and their other pinned dependencies. No third-party JAR is patched and no content registration is disabled. Three narrowly scoped lab integrations allow that closure to start on the newly released loader:

- Fugue 0.24.4 redirects reflective field calls to the removed `com.cleanroommc.hackery.ReflectionHackery` API. The lab supplies a field-access-only bridge to ImagineBreaker 3.2 and explicitly initializes declaring classes before access, preserving normal field initialization behavior.
- The 0.7 runtime omits Forge's added `BlockStateContainer.Builder`, required by GregTech fluid registration. An independently authored builder delegates to the existing block-state classes. A normal loader transformer supplies it only when no class is already present.
- `ObjectHolderRef.apply` writes registry holder fields without initializing their declaring class first, allowing a later static initializer to reset the injected value. A lab mixin performs initialization before injection.

These classes are isolated under `src/cleanroom070`, excluded from the Forge artifact and enabled in the native 0.7 environment with `-Dcubiclab.cleanroom070=true`. They qualify the tested kernel closure, not arbitrary mods or the complete historical ReflectionHackery API. Remove them only after validating the corresponding upstream/dependency fix. The production CubicChunks source is unchanged by this lab addition.

CI builds the main fork and optional lab for both loaders, runs focused checks and validates Python control code. CI does not run a graphical client. The [first measured native suite](../docs/measurements/cubic-lab-v1/README.md) includes runtime receipts, caveats and captures.

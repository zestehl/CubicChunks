# CubicChunks native profiling pass

This directory contains measured native server diagnostics, with JDK 25 Flight
Recorder samples separated from explicit workload timings. The workloads run in
disposable instances; they are not player saves. Detailed runtime and validation
context belongs to the parent port report.

The final dataset includes all eight baseline/candidate write/read runs on both
loaders and both JVMs' heightmap diagnostics. See the
[results report](../../cubic-profile-pass1.md) and
[evidence manifest](evidence/manifest.json) for outcomes, provenance and saved-world
comparisons. Raw ERROR messages are retained alongside signatures normalized
only for disposable instance roots and Java object identity suffixes.

## Evidence and charts

- `summary.json` preserves input SHA-256 hashes, complete probe results, exact UTC
  windows, event counts, method summaries, GC, recorded I/O and recorded waits.
- `workload-timings.csv` contains every original timing observation, cube counts
  and checksums. `timing-chart-data.csv` contains the chart's medians and full
  observed ranges, without treating three iterations as independent JVM runs.
  Iterations use different coordinates and have different JIT/cache state.
- `subsystems.csv` and `hotspots.csv` retain counts, allocation weights and their
  denominators. Inclusive methods overlap and must not be added together.
- `recorded-events.csv` contains observed GC, I/O and wait event summaries.
- `workload-samples.png` / `.svg` pool repeated phase windows for legibility while
  preserving individual observations in the CSV and JSON files.
- `workload-timings.png` / `.svg` show median observed duration and the full
  observed range. A single-observation save phase has no range whisker.
- `heightmap-allocation.png` / `.svg` is a **separate synthetic diagnostic** of
  three heightmap fixtures. Its JSON and two CSV files preserve exact per-thread
  allocation counter deltas, batch durations, iteration counts and output sizes.
  These exact counter measurements must not be confused with JFR allocation
  sample weights in the native workload profile.

Full-recording summaries include startup and shutdown. Workload summaries use
each probe's `startUtc` and `endUtc`; no window is inferred from a console line.
Generation/load phases request 512 cubes per iteration in three separate remote
areas. Resident lookups repeat one million accesses per iteration. Save submission
and flush cover the world's current dirty work, including spawn content, so their
reported operation counts differ from the 1,536 explicitly requested cubes.
In particular, `save_flush.operations` is pending cubes at entry; the concurrent
writer changes this count nondeterministically. Do not divide flush duration by
that count to infer throughput.

## Interpretation limits

Java execution sample counts are not elapsed CPU time or CPU utilization. Native
method samples are reported separately because they can capture threads executing
or waiting in native code. Subsystem attribution uses the first recognized frame
when scanning from leaf toward root, skipping unrecognized library frames; this
identifies a call path, not exclusive method cost. Injected methods in transformed
vanilla classes retain vanilla class attribution. The report groups overloaded
methods by class and method name.

Allocation weights estimate allocation pressure, not retained heap or exact
allocated bytes. A zero count in a short phase means no event was observed; it
does not establish that the phase made no allocations. Small phases can contain
only a handful of Java samples and cannot support precise hotspot rankings.

File I/O, monitor and park events are thresholded. Their full durations are
reported for events whose start lies in the phase; they may cross phase boundaries
and overlap across threads. Do not add them into a total wall time. GC collector
pause totals and top-level pause durations describe overlapping observations and
are kept separate. A blocking console read is not world storage latency.

Measured wall times include recorder overhead where JFR is active, JIT state,
cache state and host scheduling. Native timings on one machine, with three batches
in one process, do not establish a controlled speedup or a sustained-play result.
These observations do not cover client rendering, network play, or progression.

The heightmap diagnostic runs the same production stream writer with its legacy
default 32-byte output buffer recreated in a MethodHandle wrapper and with the
current presized buffer. Both modes receive warmup calls, alternate measurement
order and publish their result arrays so allocation escapes. The diagnostic checks
byte equality before measuring. ThreadMXBean deltas include wrapper and result
allocation. This isolates synthetic serialization behavior; it does not establish
an overall native-world speedup. Full raw elapsed timings are retained, but the
chart makes only an allocation comparison.

## Reproduction

Record the Java 25 server with the JDK's `profile.jfc` settings, an explicit
writable Flight Recorder repository, and `dumponexit=true`. Export the recording
with a sufficiently deep stack; `jfr print` defaults to only five frames:

```text
jfr print --json --stack-depth 128 --events jdk.ExecutionSample,jdk.NativeMethodSample,jdk.ObjectAllocationSample,jdk.GarbageCollection,jdk.GCPhasePause,jdk.FileRead,jdk.FileWrite,jdk.JavaMonitorEnter,jdk.ThreadPark recording.jfr
```

Save that output as UTF-8 JSON, then associate each export with its matching probe
result using an identical label. Repeated `--jfr` and `--probe` options combine
additional runs; a Forge probe may be provided without JFR.

```text
python tools/analyze_cubic_profile.py --jfr cleanroom-write=events.json --probe cleanroom-write=cubic-profile-write.json --probe forge-write=forge-probe.json --output docs/measurements/cubic-profile-pass1
python -B -m unittest discover -s tools -p test_analyze_cubic_profile.py -v
python tools/analyze_heightmap_allocation.py --log cleanroom=heightmap-cleanroom.log --log forge=heightmap-forge.log --output docs/measurements/cubic-profile-pass1
```

Python's standard library suffices for analysis with `--no-charts`. Chart exports
add matplotlib. Synthetic parser tests validate timestamp precision, selection
boundaries, sample semantics and aggregation; they are not native evidence.

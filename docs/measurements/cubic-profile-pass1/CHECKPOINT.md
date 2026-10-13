# Profiling checkpoint

Resumed and completed on 2026-10-13. Both candidate loaders now pass native
write/read checks; all eight runs and both JVMs' allocation diagnostics are
included in the current charts and summaries. The text below records the earlier
pause state. Use [the final report](../../cubic-profile-pass1.md) for current status.

Paused at the user's request on 2026-10-12. No additional parsing or rendering
was started after the pause request.

- **The native profile charts and `summary.json` are BASELINE ONLY.** They include
  Cleanroom write/read JFR and timing observations, plus Forge write/read timing
  observations. All four baseline probes passed.
- **The heightmap allocation chart is Java 25 ONLY.** Its 18 measured batches are
  a synthetic serialization diagnostic, separate from native-world/JFR evidence.
  Java 8 results exist in the build log but have not been incorporated.
- Candidate source: `5ae2e37a`. Root reports 44 tests passing per loader.
- Candidate Cleanroom native write passed. Root is finishing the active read
  process before stopping. Candidate JFR JSON exports have not been analyzed.
- Candidate Forge instance is prepared; candidate Forge native probes have not run.
- The two native charts were visually checked after fixing legend/footer overlap.
  Both analyzers are implemented; eight profile-parser semantic tests pass.
- Preserve `evidence/`, which the root agent's collector owns. Analyzer reruns
  overwrite only their named JSON/CSV/PNG/SVG outputs and do not delete directories.

Observed baseline save submission included 9 `IONbtWriter.writeBlocks` Java
samples out of 29, with heightmap allocation pressure also present. Generation
and load phases have very few samples. These counts do not establish elapsed CPU
percentages or a precise hotspot ranking. The synthetic Java 25 heightmap median
allocation fell from 10,968 to 5,256 B/call (empty), 11,032 to 5,384 (irregular),
and 93,240 to 55,016 (dense). This is not an overall native-world speedup claim.

## Resume commands

Run from `E:\WorldGenOverhaul` after completing native candidate captures and
exporting their JFR data. The candidate JSON paths below are intended output names;
at this checkpoint only the two baseline `*-jfr.json` files exist.

```powershell
.\.local\venv\Scripts\python.exe -B dev\CubicChunks-cleanroom\tools\analyze_cubic_profile.py `
  --jfr baseline-cleanroom-write=.local\cubic-profile\baseline-cleanroom-write-jfr.json `
  --probe baseline-cleanroom-write=.local\instances\cubic-profile-baseline-cleanroom-01\cubic-profile-write.json `
  --jfr baseline-cleanroom-read=.local\cubic-profile\baseline-cleanroom-read-jfr.json `
  --probe baseline-cleanroom-read=.local\instances\cubic-profile-baseline-cleanroom-01\cubic-profile-read.json `
  --probe baseline-forge-write=.local\instances\cubic-profile-baseline-forge-01\cubic-profile-write.json `
  --probe baseline-forge-read=.local\instances\cubic-profile-baseline-forge-01\cubic-profile-read.json `
  --jfr candidate-cleanroom-write=.local\cubic-profile\candidate-cleanroom-write-jfr.json `
  --probe candidate-cleanroom-write=.local\instances\cubic-profile-candidate-cleanroom-01\cubic-profile-write.json `
  --jfr candidate-cleanroom-read=.local\cubic-profile\candidate-cleanroom-read-jfr.json `
  --probe candidate-cleanroom-read=.local\instances\cubic-profile-candidate-cleanroom-01\cubic-profile-read.json `
  --probe candidate-forge-write=.local\instances\cubic-profile-candidate-forge-01\cubic-profile-write.json `
  --probe candidate-forge-read=.local\instances\cubic-profile-candidate-forge-01\cubic-profile-read.json `
  --output dev\CubicChunks-cleanroom\docs\measurements\cubic-profile-pass1

.\.local\venv\Scripts\python.exe -B dev\CubicChunks-cleanroom\tools\analyze_heightmap_allocation.py `
  --log cleanroom=.local\cubic-profile\heightmap-cleanroom.log `
  --log forge=.local\cubic-profile\cubic-forge-build.log `
  --output dev\CubicChunks-cleanroom\docs\measurements\cubic-profile-pass1
```

Then inspect the three updated PNGs, review sample-size limitations, and update
the port report. Raw elapsed timings and allocation sample weights must stay
distinct from exact ThreadMXBean deltas. Do not normalize save-flush time by the
pending-cube count: the concurrent writer makes that entry count nondeterministic.

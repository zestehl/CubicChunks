# Storage reliability and autosave pacing

This pass retains queued save data after an I/O failure, makes flush failures visible, and spreads periodic cube snapshots over world ticks. It supports Riven's allocated 32 cube levels without changing the Anvil3d format or taking over external renderer/shader responsibilities. Celeritas and Demonica work remains deferred.

## Writer ownership and recovery

Each `AsyncBatchingCubeIO` owns one daemon writer with coalesced, ordered cube/column queues. Batches default to at most 64 cubes and 16 columns. The queues keep their in-flight entries until the backend succeeds; replacement snapshots are compared by identity, not NBT value equality. A replaced coordinate moves behind older queued coordinates, so repeated writes cannot indefinitely starve another position. Publication during worker exit reschedules work without relying on vanilla's global `ThreadedFileIOBase` queue.

An IOException or backend runtime exception retains the failed batch and latches the writer failure. Automatic retries stop and the production logger reports the failure. New snapshots may replace retained data; routine autosave pauses. Explicit flush clears the latch, drains bounded batches, and forces the backend. A persistent error returns after one failed batch attempt rather than looping indefinitely. A failed drain leaves storage open for another recovery attempt. Once backend close is attempted, its disposed state and worker shutdown are recorded even if close fails.

Flush waits only for that storage writer, excluding concurrent publication through the existing world I/O lock. Interrupted barriers throw `InterruptedIOException` and preserve the interrupt flag. The anvil adapter propagates flush errors through `UncheckedIOException`, so callers no longer receive ordinary success after a failed flush. Saved-position existence checks likewise propagate I/O failure rather than reporting data absent. Pending NBT reads return deep copies before data fixing or mod loading callbacks can mutate them.

Region compression has one owner within each world writer and releases already allocated Netty buffers when another entry fails compression or key conversion. Small bounded batches keep simultaneous buffers bounded; compression no longer dispatches the entire queue onto the JVM common pool. This changes throughput/parallelism and needs measurement; it is not a general throughput improvement claim. The fallback storage API's default batch reader now retains every requested key, including null values for missing cubes/columns, rather than feeding nulls into a rejecting concurrent-map collector.

## Periodic-save pacing

A mixin marks only `MinecraftServer.tick`'s periodic `saveAllWorlds` call with an owner-thread scope. Its provider scan queues dirty coordinates and defers NBT serialization to subsequent provider ticks. Each dimension processes at most 32 cube/column coordinates per tick, with a 2 ms soft time budget. Cube/column priority alternates, including with a quota of one. A pending NBT count of 1,024 or a latched writer failure pauses this routine work and leaves remaining world data dirty.

Coordinates are resolved against current loaded objects when processed; skipped/clean/unloaded positions consume quota. The queue never retains cube objects across ticks. `disableLevelSaving` suspends continuations. Explicit save-all calls and normal unload saves still submit all required snapshots, and flush/close remain full barriers. A successful forced save clears the older continuation queue.

The settings are `autosaveSnapshotsPerTick`, `autosaveTimeMillis`, `autosavePendingThreshold`, `storageBatchCubes` and `storageBatchColumns`; batch sizes require a world restart. The time budget does not preempt one snapshot or its lighting work. Dirty-coordinate scanning, forced-save submissions, unloading and flush can still stall. The pending threshold is a routine-save pressure control, not a hard byte limit: explicit saves/unloads retain their data even when this threshold is exceeded.

## Evidence and remaining limits

Both main loader artifacts and matching optional lab artifacts passed local builds and focused regressions on Cleanroom/Java 25 and Forge/Java 8. Fault tests cover retained failures, explicit retry/recovery, equal-but-newer snapshots, fairness, publication during worker completion, pending-read isolation, interrupt reporting, force failures, null batch reads and compression-buffer cleanup. The lab guide and shared skill describe the new opt-in checks and frozen Riven input selection. No GitHub build is dispatched for a commit.

Native results are recorded separately with the exact candidate artifacts, frozen Riven input, configurations and per-side runtime. The comparison uses an explicit burst and a paced request in the same candidate, rather than implying an old-versus-new disk throughput study.

The [native storage-pacing evidence](measurements/storage-pacing/README.md) passed all six selected write/reload scenarios and independent inspection of 6,463 cubes/all 1,024 markers. Autosave processed no more than 32 coordinates per tick and finished its 1,027-coordinate queue over 34 observed ticks. Server tick p95 was 3.99 ms; its largest tick was 99.88 ms including a 98.63 ms final flush. The same-candidate explicit burst used one 316.68 ms tick. The injected pre-write fixture retained failed snapshots, reported a failed flush and persisted the newer replacement on recovery. The final durability barrier remains the main measured save stall.

Retained snapshots remain in memory, not a crash-recovery journal. Partial backend writes are not atomic as a whole batch; a retry overwrites the retained positions. Physical disk faults, power loss, natural periodic-save timing, multiworld shutdown and long stress runs are not qualified by the injected pre-write fixture. The existing read executor still has a global, best-effort shutdown; isolating reader shutdown by world remains a separate reliability task. Forge native graphical coverage remains separate from its local build/regression checks.

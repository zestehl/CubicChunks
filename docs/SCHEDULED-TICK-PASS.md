# Scheduled-tick collection repairs

This batch repairs CubicChunks' scheduled-update collections for Riven. The native baseline uses no external renderer/shader profile; Celeritas and Demonica compatibility work is deferred and its earlier failures remain retained.

## Behavior changes

- Scheduled-set iterator removal now delegates to the backing iterator and updates the per-cube index. `clear` directly clears the wrapped backing set. The earlier nonempty clear/removal operations threw `UnsupportedOperationException`.
- Set equality/hash behavior now follows `AbstractSet`. Bulk removal handles self-removal and snapshots its input to support aliased per-cube bucket views while retaining work proportional to the supplied removal entries. That reference-array allocation is a correctness cost, not an allocation-reduction claim.
- Scheduled-list replacement returns the previous entry. Bucket removal uses the actual stored occurrence, preserving different scheduled times/priorities when two entries compare equal.
- Structural list edits maintain `modCount` and use inherited indexed iterators. List iterators and sublists now detect structural changes, and iterator removal after a nonstructural replacement removes the current entry from both indexes.

The existing equals/ordering collision workaround remains intact. The indexed scheduled-tick format, vanilla ordering/throttling and cube NBT fields are unchanged. The exposed per-cube bucket views remain mutable and can bypass global index maintenance; this batch does not redesign that public surface.

## Validation

Cleanroom/Java 25 and Forge/Java 8 main artifacts passed local builds and focused regressions. The new cases exercise clear/reuse, iterator-state checks, bulk/self/aliased removals, retention, colliding entries with changed times, replacement, duplicate occurrence identity, list-iterator edits and sublist invalidation. Optional lab artifacts also passed their matching builds/checks. These builds qualified the code batch; no GitHub build was dispatched for a commit.

The named-class opportunity probe now reports completed scheduled-set clear/removal and correct list replacement returns on both JVMs. Its other audit findings remain open; successful collection observations do not qualify a whole game or a speedup.

The native `scheduled-pass-01` fixture passed **64 real vanilla state transitions across all 32 allocated cube levels** in height **[−128,384)**. It schedules duplicate unlit-redstone-torch and contained-flowing-water requests, verifies one live/serialized pending entry per block in the actual cube writer, observes lit torches/still water, and checks consumed entries disappear from the cube index. Original fixture block states are restored through the world API. Five selected write/read scenarios passed with unobstructed client captures and normal process exits; fresh JVMs recovered all 1,024 gold markers. Independent stopped-world inspection verified 6,463 saved cubes and all markers.

[Exact results and evidence](measurements/scheduled-tick-contracts/README.md) record artifact/source hashes, the functional checks and their limits. The new runtime was selected only after the latest-release preflight rejected the stale pin: Cleanroom **0.7.1-alpha**, with reviewed SAS/SDL fixes and lwjgly 1.0.2. Its client/server universal bytes match the reviewed release. Development compilation and the active Riven profile stay on **0.6.13-alpha**; the existing isolated lab overlays remain selected for the reviewed 0.7.1 native runtime.

## Remaining limits

This is a collection/functional repair, not evidence of improved streaming TPS. The native run uses an independently changed Riven artifact and a different runtime/workload from the previous profile, with no JFR recording or controlled timing comparison. The scheduled fixture verifies pending NBT serialization and actual callbacks, but not delayed-tick durability across a disk restart, unrestricted fluid propagation, arbitrary mods or long-running stress. Forge has local artifact/regression coverage; the new graphical fixture uses Cleanroom.

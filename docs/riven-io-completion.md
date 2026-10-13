# I/O completion ownership

This branch hardens asynchronous load completion for Minecraft 1.12.2 at
upstream commit `53847757c7998f3541fccc8c9b5d23dd23e4077d`. It preserves
upstream licensing and attribution and leaves native world mutation on the
server thread.

## Behavior

A completed column or cube load remains discoverable while its native load
events and consumers run. A request for the same coordinates during those
events can join that load. The tick completion path claims each task once,
so a callback that reenters the tick cannot complete it again. Finally, it
removes only the exact task it completed; a replacement queued by a callback
keeps its ownership.

Each callback is removed before invocation. If a consumer throws a
`RuntimeException`, the remaining consumers, including ownership cleanup,
still run. The first exception is rethrown with distinct later failures
attached as suppressed exceptions. `Error` remains immediately fatal;
remaining callbacks are not invoked, and the task is released in `finally`.

This does not make the public loading methods safe to call from arbitrary
worker threads. The existing synchronous load path and native load-event
reentrancy still require separate runtime qualification. In particular,
this change does not claim to fix recursively loading the same cube from
`CubeDataEvent.Load`. It does not change saving, session locks, terrain,
lighting, or chunk registration ownership.

## Validation

`TestAsyncTaskCompletion` covers reentrant completion, joining a load during
completion, callback failures, replacement tasks, added and removed
callbacks, incomplete jobs, and fatal errors. Run it through the upstream
build using a compatible Gradle launcher JDK:

```text
./gradlew test --tests io.github.opencubicchunks.cubicchunks.core.server.chunkio.async.forge.TestAsyncTaskCompletion
```

The focused tests also passed when the actual provider and completion helper
sources were compiled with `--release 8` and run on Java 8 and Java 25. That
isolated run supplied only a compile-time fixture for the MCP nullability
annotation; it did not construct a Minecraft world or substitute loading
behavior. Applying the tests to the original callback implementation and
original tick-loop behavior reproduces failures.

The three changed production classes also compile against the pinned
CubicChunks binary and the mapped Cleanroom 0.6.13-alpha and Forge
14.23.5.2860 APIs, producing Java 8 bytecode. These focused checks are not a
full mod build or a native runtime test.

The upstream Gradle test task was attempted with Gradle 8.2 and JDK 17.
Both the online attempt and an offline retry waited inside ForgeGradle's
HTTPS download of the pinned Forge universal artifact and were deliberately
stopped. The resulting daemon-disappeared messages reflect that cancellation;
they are not evidence of a spontaneous build crash. The full upstream build
and test task have not passed.

A subsequent retry used the verified official universal JAR already present
in the local Gradle cache. It advanced to downloading Forge's sources JAR,
which was not cached, and was stopped at that dependency boundary. No
upstream JAR contents or build configuration were changed.

This branch has not been installed into Riven's runtime. Its pinned
CubicChunks binary remains unchanged. Native world load, save/restart,
mod-event compatibility, and performance acceptance remain pending.

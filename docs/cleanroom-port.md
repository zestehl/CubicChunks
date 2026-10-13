# Cleanroom and Java 25 development

This fork targets Minecraft 1.12.2 on Cleanroom 0.6.13-alpha / JDK 25.
Forge 14.23.5.2860 / Java 8 remains an explicit fallback artifact. Both use
the upstream CubicChunks API and source tree, including the earlier
[asynchronous completion ownership fix](riven-io-completion.md).

The isolated `cleanroom/` project uses the Cleanroom Unimined conventions.
The repository's original ForgeGradle project is preserved. Build each
artifact with a JDK 25 launcher:

```sh
cd cleanroom
./gradlew build
./gradlew -PcubicLoader=forge build
```

Use `gradlew.bat` on Windows. The remapped runtime JARs are under
`cleanroom/build/cleanroom/libs` and `cleanroom/build/forge/libs`. The
`*-dev.jar` files are development outputs, not native runtime artifacts.

The port does not bundle Mixin into Cleanroom. The Forge fallback uses
MixinBooter. Minecraft mods belong in remapped mod configurations; ordinary
Java libraries remain separate. Native world mutation, lighting, event
publication and saving keep their existing thread ownership.

The bundled RegionLib is the hash-verified maintainer publication
`0.78.0-20210527.114505-2`; its matching source revision and license are
recorded under `cleanroom/licenses/regionlib`. The old flow-noise embed
has no uses in the mod or API and is omitted. Addons that implicitly relied
on that bundled library have not been qualified.

The port supplies MCP nullability metadata for compilation only. It does
not bundle that shim, Minecraft classes, or Mixin. Soft-interface bridges
preserve the public CubicChunks names while vanilla methods are remapped;
the overloaded pathfinding injection now identifies its exact target.

## Java 25 watchdog

The vanilla compatibility generator's watchdog previously called
`Thread.stop()`, which throws on Java 25. It now records one diagnostic per
active nested generation operation and keeps at most 32 recent stack
samples. Reports remain available to Minecraft's crash-report callable.
This policy applies to both artifacts: the watchdog does not stop or
interrupt the generation thread. Fatal recovery from a truly stuck
generator requires the server's watchdog or external supervision.

The Riven cube generator does not use this vanilla compatibility watchdog.
Its state transitions have focused tests; native timeout recovery is not
qualified by Riven's generation tests.

## Build validation

Both source-built remapped artifacts pass the focused async-completion,
hash-distribution and watchdog tests on their target JVMs. Build checks
also verify Java 25 / Java 8 bytecode, the six mixin configurations and
generated refmaps, public API naming, library checksums and packaging.
The original LaunchWrapper-based upstream test suite is not part of this
new test task and has not passed here.

## Cube lookup hash

The old queued-cube hash multiplied Y by Z. At Z=0, every Y for a fixed X
and world had the same hash; at Y=0, every Z had the same hash. Mixing each
coordinate independently removes these predictable collision planes in
the async cube task map. Equality and saved-world keys are unchanged.

The [synthetic diagnostic](measurements/hash-distribution/README.md)
measures hash and bucket distributions for fixed coordinate sets. It does
not measure lookup latency, native generation, disk I/O, server throughput
or frame rate. Both Java 25 and Java 8 produce the same measured distributions.

![Measured synthetic hash distributions](measurements/hash-distribution/hash-distribution.png)

## Riven integration

Use a fresh instance for each changed artifact and record the actual JAR
hash. Riven's normal dependency pin and previous worlds remain separate
from fork experiments. The current Riven held-map integration supplies
`common.MixinItemMap` under CubicChunks' package, satisfying an upstream
configuration entry whose source is absent from CubicChunks. That entry
is retained so this integration continues to load. Standalone CubicChunks
without that bridge still has the known missing optional map mixin.

Full native validation results and remaining limitations are recorded
below after the first source-built artifacts are exercised.

# First lighting and configuration pass

This candidate fixes two lighting-data/work issues and restores the existing vanilla vertical-render-distance option. External Celeritas and Demonica code and JARs remain independently owned inputs. The GitHub workflows remain manual; source changes were validated locally as one candidate batch, not triggered by commits.

## Behavior changes

- `LightingManager.writeToNbt` clones the column's `LastHeightMap` before passing it to Minecraft NBT. NBT retains input arrays, so a queued/compressed snapshot must not reference a column array that can change later. The added 256-int copy is a correctness cost, not an allocation reduction claim.
- Surface tracking now notifies each X/Z column once, retaining the legacy 17 × 17 footprint and its positive X/Z edge. The old 17 × 17 × 17 traversal repeated identical column updates along Y. Calls per tracked cube fall from **4,913 to 289**; the set of affected coordinates remains unchanged. Relight scheduling and light values remain the same.
- `VERT_RENDER_DISTANCE` now names the current `client.vertviewdist` mixins, including the no-OptiFine variant. Its old class names did not match the registered mixins, so the configured option could not reliably disable them. The default remains enabled and the mod-dependency conditions still apply.

This option repair is not a Celeritas height/data adapter. A deliberate `--vanilla-vertical-render-distance off` lab preparation records a supported CubicChunks configuration choice for diagnosis. The [external-renderer baseline blockers](RENDERER-COMPATIBILITY.md) and full-height qualification remain separate requirements.

## Validation

Local main and optional lab builds passed for Cleanroom/Java 25 and Forge/Java 8. Focused checks compare the new notification coverage against the legacy traversal at negative, zero and high coordinates, reject duplicate notifications, and verify option off/on/dependency gating against the actual current mixin names. Existing remapped-artifact and regression checks also passed.

The first test compilation exposed that the focused test compile classpath lacked the named Minecraft/Mixin APIs. It now uses the same main compile classpath already used by the tests at runtime. No ordinary runtime mod dependency was added.

The lab includes `lighting-snapshot`, which calls the actual cube-to-NBT writer at the lower/upper fixture ends. It requires the lighting height array to be independent, temporarily perturbs and restores the live column height value, and checks the serialized snapshot remains unchanged. No storage save is queued during the perturbation. Its normal save events indicate serialization, not disk durability.

The batch passed 47 main regressions per loader, six Cleanroom lab checks and four Forge lab checks. After refining the option regression to derive registered class names from the actual mixin configuration, that focused test passed again on Java 25 and Java 8 without repackaging the unchanged candidate JARs. Ten Python control checks and eight profile-analyzer checks passed. Previous main/lab artifacts for both loaders are preserved with hashes under `.local/cubic-lab/lighting-batch-baseline`; candidate build logs are `.local/cubic-lab/lighting-batch-*-build.log`.

The native `lighting-pass-01` baseline passed all **eleven scenarios** with real rendered frames and zero GUI-covered frames. Lower/upper lighting snapshots remained independent, fresh-JVM synchronous/asynchronous loads recovered all 1,024 markers, and independent stopped-world inspection verified 9,416 serialized cubes and those same 1,024 markers. [Measured report, graphs and captures](measurements/lighting-first-pass/README.md) retain exact input hashes and timing limits. Input review found server product `0.7.0` and client product `0.7.0-alpha`: upstream replaced assets under the same release tag while the old server product was still obtainable. This evidence retains that exact mixed-runtime limitation, rather than being relabeled as the current matched-runtime default.

The initial one-tick snapshot diagnostic captured one frame interval and no completed client-tick timing. Reporting now leaves that optional metric empty instead of failing; it remains a correctness check, not a useful percentile benchmark.

A fresh **matched `0.7.0-alpha` client/server** baseline, `lighting-pass-02`, also passed all eleven scenarios and independent inspection of all 1,024 markers and 9,416 cubes. Both installed runtime JARs match the reviewed universal SHA-256. It reused the same CubicChunks/lab binaries and picked up Riven's independently updated prebuilt artifact; its [current-runtime report](measurements/lighting-current-runtime/README.md) is separate from the initial descriptive run. No additional mod build or GitHub build was needed for this runtime correction.

The repaired option also permits a Celeritas-only startup/join diagnostic when explicitly off. The [actual captures](measurements/renderer-option-diagnostic/README.md) show empty sky without the baseline terrain/markers despite expected packet/load counts and intact stored markers. Rendering remains unqualified, and neither external mod was patched.

## Measurement limits

The 17-fold reduction is a code-derived notification count, not a 17-fold server-speed claim. Native tick/frame observations include Riven generation, autosaves, scheduling and instrumentation. One run is descriptive; old runs with a different Riven artifact or changed phase sequence are not a controlled performance baseline. Renderer/shader compatibility requires actual terrain/light/entity coverage after startup succeeds, even when storage and snapshot checks pass.

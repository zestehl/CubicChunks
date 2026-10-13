# External renderer and shader compatibility environment

Status: renderer/shader compatibility work is deferred at the user's request. Preserve these inputs and failed checks as evidence; use the baseline renderer for ongoing CubicChunks/Riven improvements. No Celeritas or Demonica patch was made during the preliminary compatibility investigation.

Checked October 13, 2026. Celeritas and Demonica are now pinned as **optional client-only lab inputs**, with reusable preparation profiles, separate client/server hash checks, attribution and dependency reasons. Native startup checks reveal existing compatibility blockers before any new optimization is applied. The configurations are installed and reproducible; **a joined/rendered CubicChunks world with this pair is not yet qualified**.

Follow-up: the [first CubicChunks lighting/configuration batch](LIGHTING-FIRST-PASS.md) repairs the existing `VERT_RENDER_DISTANCE` option. A [Celeritas-only diagnostic with that option off](measurements/renderer-option-diagnostic/README.md) now joins and completes bounded streaming captures on matched product `0.7.0-alpha`. Both final captures show empty sky where the baseline has terrain/markers, despite the expected cube packet/load counts. Startup is improved; terrain rendering is still not qualified. The external mods remain unchanged, and the Demonica pair was not rerun in this follow-up.

This work does not import renderer/shader code into CubicChunks, patch either project's source/JARs, or assume maintenance of their implementations. Reference checkouts stay separate under `E:\WorldGenOverhaul\research`; the default baseline and dedicated-server dependency closure are preserved.

## Exact inputs

| Input | Selection and provenance |
| --- | --- |
| Demonica | Published `0.7.3`, release tag `v0.7.3`, source commit `705f596e7800d3dca20a61dd74753d7586beabc1`; SHA-256 `0b13f26d02d2b6081b8d6b7c913d207485052f3b39a182f9069e978e581c4b1d`, checked against the release `SHA256SUMS` and downloaded bytes |
| Celeritas | Upstream commit `9b661b70ecaf84c39052e8fbc51c875ba37e739d`, Maven `2.5.0-autobuild.9b661b70`; SHA-256 `5bf123a6da6190f6e061cd3fd069a2bddcbf6ebf57894381b6c888c06a94f982`, matching Demonica's embedded runtime pin and its published pin record |
| Initial startup matrix runtime | Cleanroom release tag `0.7.0-alpha`, original product `0.7.0`, Java 25; exact prior CubicChunks and optional lab artifacts reused |
| Current preparation pin | Same release tag, replacement product `0.7.0-alpha`; asset names/hashes reviewed after upstream replacement at 15:13 UTC. New preparations verify both installed universal JARs. Original environment receipts remain unchanged. |
| Loader comparison | Separate Cleanroom `0.6.13-alpha` / Java 25 environment, explicitly selected because Demonica documents testing with 0.6.12/0.6.13 |

[Demonica's release](https://github.com/ndellagrotte/Demonica/releases/tag/v0.7.3) provides the mod binary. Its [pin record](https://github.com/ndellagrotte/Demonica/blob/705f596e7800d3dca20a61dd74753d7586beabc1/docs/celeritas/PIN.md) names the accepted Celeritas build and both accepted artifact hashes. A different Celeritas SHA disables Demonica shaders, so choosing upstream HEAD would not be an equivalent combined test. Celeritas's [upstream README](https://git.taumc.org/embeddedt/celeritas/src/commit/9b661b70ecaf84c39052e8fbc51c875ba37e739d/README.md) distributes source rather than official mod binaries; the selected third-party auto-build is the one expressly consumed by Demonica. Its source origin remains upstream Celeritas, not a CubicChunks fork of that renderer.

The profile retains the binaries' bundled notices, including Demonica's S8TNLib classes and contained libraries. There is no separate S8TNLib mod addition. [client-renderers.json](../lab/profiles/client-renderers.json) records URLs, source commits, SHA-256, independent SHA-1, licenses, reasons and selected dependencies. Optional client reasons are also registered in Riven's `dev/profiles/worldgen.json`, outside its active `mods` lists.

## Native startup matrix

| Retained environment | Client inputs | Outcome |
| --- | --- | --- |
| `renderer-pair-01` | Celeritas + Demonica, Cleanroom 0.7.0 | Client exits before world join: `NoClassDefFoundError: org/lwjgl/glfw/GLFW` from bundled GLSM `Lwjgl3GLRenderBackend.getContextHandle`, through Demonica's GL initialization. The runtime is SDL3-based; this binary expects GLFW. |
| `renderer-pair-0613-01` | Same exact mod pair, Cleanroom 0.6.13-alpha | Demonica's Celeritas hash guard accepts the binary and GL initialization progresses. Client then exits before join: CubicChunks' required `onGetRenderDistance` redirect in `client.vertviewdist.MixinRenderGlobal` finds no required target in `setupTerrain`. |
| `renderer-celeritas-01` | Celeritas alone, Cleanroom 0.7.0 | Same CubicChunks redirect fails with `(0/1) succeeded`. This isolates the renderer/mixin conflict independently of Demonica's GLFW issue. |

All three initial dedicated servers reached readiness and were stopped by the owned runner's failure cleanup. Each failed client/server environment, bootstrap world, logs and available crash reports are retained. No write/read measurement suite began for these three environments, and they have no qualified performance results or actual world captures. Existing recipe/advancement/signature diagnostics remain distinguishable from the fatal exceptions above. The later option-off diagnostic has separate inputs/captures and failed terrain-rendering qualification as described above.

The [evidence manifest](measurements/renderer-compatibility/observations.json) records input inventories, release/runtime selection, artifact hashes, log/crash hashes, preparation state and the separate failure classifications. Raw files are under `.local/cubic-lab/<name>/runs/prime` and each client's `crash-reports`. The corresponding server is `.local/instances/cubic-lab-<name>`. Initial unprimed Prism bundles exist for all three configurations; they carry the same startup limitations.

## Responsibility and interface boundaries

| Owner | Contract to preserve during CubicChunks optimization |
| --- | --- |
| CubicChunks | Cube coordinates/storage/persistence; world build bounds; block-light/skylight values; heightmap and relight semantics; world-thread mutation and immutable save snapshots; notifications that mark affected geometry dirty |
| Celeritas | Terrain section gathering/snapshots, mesh scheduling and rendering, AO/light sampling in its mesher, vertex formats and renderer caches |
| Demonica | Iris shader pipeline, GLSM state management, lightmap/vertex interpretation, terrain/shadow/composite passes and its supported Celeritas patch contract |

Preserve the light values and section data they consume, rather than changing shader behavior to hide a lighting regression. Storage snapshot and server height-notification improvements remain owned by CubicChunks. Changes to packet application and render invalidation need an external-renderer check as well as the vanilla-renderer baseline. An optimization of CubicChunks' vanilla `RenderCubeCache` may not run on Celeritas's active meshing path.

Two concrete source interactions matter:

1. CubicChunks' [vertical-distance RenderGlobal mixin](../src/main/java/io/github/opencubicchunks/cubicchunks/core/asm/mixin/selectable/client/vertviewdist/MixinRenderGlobal.java) redirects a vanilla field read in a method Celeritas replaces. This is the fatal interaction reproduced above. Demonica's pinned `EntityRendererIrisMixin` separately uses composable optional expression modifiers around render-distance reads and explicitly discusses CubicChunks coexistence; that does not solve the different `RenderGlobal` failure.
2. Celeritas's pinned 1.12.2 frontend reports a minimum build height of **0**, indexes `Chunk.getBlockStorageArray()` by section Y, and treats negative indices as absent in cloned-section acquisition. CubicChunks owns a separate `CubeMap` and the lab's range is **[−128,384)**. These are interface assumptions requiring coverage before claiming full-height compatibility. They are source concerns here: startup stops before they can be exercised in a rendered world.

Relevant unmodified source is in `research/Celeritas-demonica-pin/forge122/src/main/java/org/taumc/celeritas/impl/render/terrain/CeleritasWorldRenderer.java`, `VintageRenderSectionManager.java`, `impl/world/WorldSlice.java`, `impl/world/cloned/ClonedChunkSection.java`, and `research/Demonica-0.7.3/src/main/java/com/demonica/mixin/features/iris/EntityRendererIrisMixin.java`. Latest upstream references are also retained in the separate `research/Celeritas` and `research/Demonica` checkouts. No production code from those checkouts was modified or copied into the fork.

## Repeatable operations and next qualification

```powershell
# From E:\WorldGenOverhaul. Pick new names; failed environments are evidence.
.local/venv/Scripts/python.exe -B dev/CubicChunks-cleanroom/tools/cubic_lab.py prepare --name renderer-next --client-profile celeritas-demonica --port 25591
.local/venv/Scripts/python.exe -B dev/CubicChunks-cleanroom/tools/cubic_lab.py prime --name renderer-next

# Explicit loader comparison; does not change the default runtime pin.
.local/venv/Scripts/python.exe -B dev/CubicChunks-cleanroom/tools/cubic_lab.py prepare --name renderer-0613-next --client-profile celeritas-demonica --runtime-release 0.6.13-alpha --port 25591
```

Use `--client-profile celeritas` to isolate the renderer and the default `baseline` for the retained conventional client path. Do not run measurement pairs simultaneously on this host. Separate client and server hash inventories prevent accidentally installing either addon on the server and preserve earlier baseline manifests. The mod set must remain immutable for a prepared revision.

`--vanilla-vertical-render-distance off` now selects a working CubicChunks option, with the choice recorded in the manifest and client configuration. It skips these optional vanilla distance hooks through their existing configuration contract; required core injections remain enforced. It does not supply the cube-to-section data contract needed by the external renderer. The default remains enabled.

The remaining startup work is an explicit compatibility requirement, not a new performance regression or a completed renderer integration. Do not suppress required injections, import another renderer's implementation, change a third-party JAR, or silently narrow height to turn these runs into PASS. Record the CubicChunks renderer-hook collision and the external GLFW/SDL loader boundary while choosing a supported interoperability path.

After startup is resolved within the chosen ownership boundary, qualification needs real rendered terrain and lighting at negative Y, ordinary height and above 255; edits/emissive sources across cube boundaries; unload/reload and dirty-mesh propagation; tile/entity rendering; and shaders actually enabled when testing Demonica's shader passes. Add those workloads to the lab and keep pins/guide/skill aligned. Until then, existing happy-path storage/timing tests cannot be presented as renderer or shader compatibility.

## Build allocation policy

GitHub build workflows on the working fork branch are now **manual dispatch only**. The legacy publishing workflow also retains its `MC_1.12` branch guard. The trigger change is published as `efe88f68`; no build was dispatched for this integration. Local Python/profile checks and native launches used existing verified CubicChunks, lab and Riven artifacts. Build Java changes and validate the relevant artifacts when needed; do not rebuild merely because a commit was made.

package io.github.opencubicchunks.cubicchunks.lab;

import io.github.opencubicchunks.cubicchunks.api.util.CubePos;
import io.github.opencubicchunks.cubicchunks.core.CubicChunksConfig;
import io.github.opencubicchunks.cubicchunks.core.server.AutosaveScope;
import io.github.opencubicchunks.cubicchunks.core.world.cube.Cube;
import net.minecraft.init.Blocks;
import net.minecraft.util.math.BlockPos;
import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Same dirty fixture for paced and explicit saves. Preparation completes before capture starts. */
final class LabSavePacing {
    private final List<Integer> pending = new ArrayList<>();
    private int maxProcessed, initialPending;
    private boolean issued;

    void prepare(LabJob job) throws IOException {
        job.provider.saveChunks(true); job.provider.getCubeIO().flush();
        for (CubePos pos : job.targets) {
            Cube cube = job.provider.getLoadedCube(pos);
            cube.setBlockState(new BlockPos(pos.getMinBlockX() + 8, pos.getMinBlockY() + 8, pos.getMinBlockZ() + 8), Blocks.GOLD_BLOCK.getDefaultState());
            cube.markDirty();
        }
    }

    boolean tick(LabJob job) throws IOException {
        if (!issued) {
            long start = System.nanoTime();
            if (job.scenario.equals("autosave")) AutosaveScope.run(() -> job.provider.saveChunks(true));
            else job.provider.saveChunks(true);
            job.submissionNanos = System.nanoTime() - start;
            job.operations.add(job.submissionNanos); initialPending = job.provider.getPendingAutosaveCount();
            issued = true;
        } else {
            int processed = job.provider.getLastAutosaveProcessedCount();
            if (processed > CubicChunksConfig.autosaveSnapshotsPerTick) throw new IllegalStateException("Autosave snapshot quota exceeded");
            maxProcessed = Math.max(maxProcessed, processed);
        }
        int remaining = job.provider.getPendingAutosaveCount(); pending.add(remaining);
        if (remaining > 0) return false;
        for (CubePos pos : job.targets) if (job.provider.getLoadedCube(pos).needsSaving()) throw new IllegalStateException("Fixture cube remains dirty after save " + pos);
        long start = System.nanoTime(); job.provider.getCubeIO().flush(); job.flushNanos = System.nanoTime() - start;
        job.operationCount = job.targets.size();
        return true;
    }

    Map<String, Object> summary() {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("initialPendingCoordinates", initialPending); result.put("pendingCoordinatesByTick", pending);
        result.put("maxProcessedCoordinatesPerTick", maxProcessed);
        result.put("configuredEntryLimit", CubicChunksConfig.autosaveSnapshotsPerTick);
        result.put("softBudgetMillis", CubicChunksConfig.autosaveTimeMillis);
        result.put("pendingNbtThreshold", CubicChunksConfig.autosavePendingThreshold);
        result.put("boundary", "Same candidate, dirty 1024-cube fixture; explicit burst and paced periodic saves have different latency semantics. Individual snapshots and scans can exceed the soft budget.");
        return result;
    }
}

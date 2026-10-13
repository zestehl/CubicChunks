package io.github.opencubicchunks.cubicchunks.lab;

import io.github.opencubicchunks.cubicchunks.api.util.CubePos;
import io.github.opencubicchunks.cubicchunks.api.world.ICubeProviderServer.Requirement;
import io.github.opencubicchunks.cubicchunks.api.world.ICubicWorld;
import io.github.opencubicchunks.cubicchunks.core.CubicChunksConfig;
import io.github.opencubicchunks.cubicchunks.core.server.CubeProviderServer;
import io.github.opencubicchunks.cubicchunks.core.util.ticket.ITicket;
import io.github.opencubicchunks.cubicchunks.core.world.cube.Cube;
import net.minecraft.entity.player.EntityPlayerMP;
import net.minecraft.init.Blocks;
import net.minecraft.server.MinecraftServer;
import net.minecraft.util.math.BlockPos;
import net.minecraft.util.text.TextComponentString;
import net.minecraft.world.GameType;
import net.minecraft.world.WorldServer;
import java.nio.file.Path;
import java.time.Instant;
import java.util.*;

/** Work is bounded per tick. Only the explicitly named flush phase blocks for storage completion. */
final class LabJob {
    private static final ITicket RETAIN = () -> false;
    private static final Map<CubePos, Cube> held = new LinkedHashMap<>();
    final MinecraftServer server;
    final WorldServer world;
    final CubeProviderServer provider;
    final String scenario, id = UUID.randomUUID().toString();
    final Path output;
    final Set<UUID> peers = new HashSet<>(), ready = new HashSet<>();
    final List<CubePos> targets = new ArrayList<>();
    final Map<CubePos, java.util.function.Consumer<Cube>> subscriptions = new HashMap<>();
    final Samples ticks = new Samples(), operations = new Samples();
    final LabHooks.PacketCounters packets = new LabHooks.PacketCounters();
    final int minY, maxY, initialCubes;
    final long created = System.nanoTime();
    long started, ended, operationCount, dataLoads, dataSaves, cubeLoads, cubeUnloads, flushNanos, submissionNanos, lookupChecksum;
    long[] gcStart;
    String startUtc, failure;
    int warmup = 40, progress, elapsedTicks, outstanding, completedAsync;
    boolean controlSent, done;

    LabJob(MinecraftServer server, String scenario) {
        if (!Arrays.asList("idle", "generate", "resident", "save", "load-sync", "load-async", "horizontal", "vertical", "lighting-snapshot").contains(scenario))
            throw new IllegalArgumentException("Unknown lab scenario");
        this.server = server; this.scenario = scenario; world = server.getWorld(0);
        ICubicWorld cubic = (ICubicWorld) world;
        if (!cubic.isCubicWorld()) throw new IllegalArgumentException("Lab requires a cubic overworld");
        minY = cubic.getMinHeight(); maxY = cubic.getMaxHeight();
        if (minY != -128 || maxY != 384) throw new IllegalArgumentException("Expected Riven test bounds [-128,384)");
        provider = (CubeProviderServer) world.getChunkProvider(); initialCubes = provider.getLoadedCubeCount();
        output = server.getFile("cubiclab-results").toPath().resolve(id);
        for (EntityPlayerMP player : server.getPlayerList().getPlayers()) {
            if (player.dimension == 0) peers.add(player.getUniqueID());
        }
        if ((scenario.equals("horizontal") || scenario.equals("vertical")) && peers.isEmpty())
            throw new IllegalArgumentException("Streaming tests require an in-game player");
        // Two separate cohorts permit independent process-reload sync and async tests.
        for (int cohort = 0; cohort < 2; cohort++) {
            if (scenario.equals("load-sync") && cohort != 0 || scenario.equals("load-async") && cohort != 1) continue;
            for (int x = 128 + cohort * 32; x < 132 + cohort * 32; x++)
                for (int z = 128; z < 132; z++) for (int y = minY >> 4; y < maxY >> 4; y++) targets.add(new CubePos(x, y, z));
        }
        if (scenario.startsWith("load-")) for (CubePos pos : targets) {
            if (provider.getLoadedCube(pos) != null) throw new IllegalArgumentException("Reload cohort already resident; restart and keep players at spawn");
        }
        if (scenario.equals("resident") || scenario.equals("save") || scenario.equals("lighting-snapshot")) for (CubePos pos : targets) {
            if (provider.getLoadedCube(pos) == null) throw new IllegalArgumentException("Generate the fixture first");
        }
    }
    void tick() throws java.io.IOException {
        if (done) return;
        if (System.nanoTime() - created > 180_000_000_000L) { failure = "Scenario timed out"; done = true; return; }
        if (warmup-- > 0) return;
        if (!controlSent) {
            for (EntityPlayerMP player : server.getPlayerList().getPlayers()) if (peers.contains(player.getUniqueID()))
                Network.CHANNEL.sendTo(new Network.ClientMessage(CubicLab.control("start", id, scenario)), player);
            controlSent = true;
        }
        if (!ready.containsAll(peers)) return;
        if (started == 0) { started = System.nanoTime(); startUtc = Instant.now().toString(); gcStart = LabData.gc(); LabHooks.serverPackets = packets; }
        elapsedTicks++;
        switch (scenario) {
            case "idle": done = elapsedTicks >= 100; break;
            case "lighting-snapshot":
                for (CubePos pos : Arrays.asList(targets.get(0), targets.get(targets.size() - 1))) {
                    long snapshotStart = System.nanoTime();
                    io.github.opencubicchunks.cubicchunks.core.server.chunkio.LabLightingSnapshotProbe.verify(provider.getLoadedCube(pos));
                    operationCount++; operations.add(System.nanoTime() - snapshotStart);
                }
                done = true; break;
            case "resident":
                long before = System.nanoTime();
                for (int i = 0; i < 10000; i++) {
                    CubePos pos = targets.get((int) ((operationCount + i) % targets.size()));
                    Cube cube = provider.getLoadedCube(pos);
                    if (cube == null) throw new IllegalStateException("Resident cube disappeared");
                    lookupChecksum += cube.getY();
                }
                operations.add(System.nanoTime() - before); operationCount += 10000;
                done = elapsedTicks >= 100; break;
            case "horizontal": case "vertical":
                if ((elapsedTicks - 1) % 40 == 0) {
                    int step = (elapsedTicks - 1) / 40;
                    for (EntityPlayerMP player : server.getPlayerList().getPlayers()) if (peers.contains(player.getUniqueID())) {
                        player.setGameType(GameType.SPECTATOR);
                        double x = scenario.equals("horizontal") ? 2048 + step * 256 : 2048;
                        double y = scenario.equals("vertical") ? LabRoute.height(minY, maxY, step) : 80;
                        player.connection.setPlayerLocation(x + .5, y, 2048.5, 0, 15);
                    }
                    progress++; operationCount++;
                }
                done = elapsedTicks >= 240; break;
            case "load-async":
                while (progress < targets.size() && outstanding < 16) {
                    CubePos pos = targets.get(progress++); outstanding++;
                    long requestStarted = System.nanoTime();
                    java.util.function.Consumer<Cube> consumer = cube -> {
                        subscriptions.remove(pos);
                        if (done) return;
                        outstanding--; completedAsync++; operationCount++;
                        try { checkCube(cube, pos, true); retain(cube); }
                        catch (Exception error) { failure = error.toString(); }
                        operations.add(System.nanoTime() - requestStarted);
                    };
                    subscriptions.put(pos, consumer);
                    provider.asyncGetCube(pos.getX(), pos.getY(), pos.getZ(), Requirement.LOAD, consumer);
                }
                done = completedAsync == targets.size(); break;
            default:
                for (int count = 0; count < 8 && progress < targets.size(); count++) {
                    CubePos pos = targets.get(progress++);
                    long begin = System.nanoTime();
                    if (scenario.equals("save")) {
                        Cube cube = provider.getLoadedCube(pos);
                        checkCube(cube, pos, false);
                        // Deliberate marker updates are fixture preparation, outside submission timing.
                        cube.setBlockState(marker(pos), Blocks.GOLD_BLOCK.getDefaultState()); cube.markDirty();
                        begin = System.nanoTime(); provider.getCubeIO().saveCube(cube);
                        long cost = System.nanoTime() - begin; submissionNanos += cost; operations.add(cost);
                    } else {
                        Cube cube = provider.getCubeNow(pos.getX(), pos.getY(), pos.getZ(),
                            scenario.equals("generate") ? Requirement.GENERATE : Requirement.LOAD);
                        checkCube(cube, pos, scenario.equals("load-sync")); retain(cube);
                        operations.add(System.nanoTime() - begin);
                    }
                    operationCount++;
                }
                if (progress == targets.size()) {
                    if (scenario.equals("save")) {
                        long begin = System.nanoTime(); provider.saveChunks(true); submissionNanos += System.nanoTime() - begin;
                        begin = System.nanoTime(); provider.getCubeIO().flush(); flushNanos = System.nanoTime() - begin;
                    }
                    done = true;
                }
        }
    }
    private static BlockPos marker(CubePos pos) { return new BlockPos(pos.getX() * 16 + 8, pos.getY() * 16 + 8, pos.getZ() * 16 + 8); }
    private void checkCube(Cube cube, CubePos pos, boolean saved) {
        if (cube == null || !cube.getCoords().equals(pos)) throw new IllegalStateException("Missing/wrong cube " + pos);
        if (saved && cube.getBlockState(marker(pos)).getBlock() != Blocks.GOLD_BLOCK) throw new IllegalStateException("Stored marker missing " + pos);
    }
    private static void retain(Cube cube) {
        cube.getTickets().add(RETAIN); held.put(cube.getCoords(), cube);
    }
    static void release() { for (Cube cube : held.values()) cube.getTickets().remove(RETAIN); held.clear(); }
    void finish() {
        done = true;
        for (Map.Entry<CubePos, java.util.function.Consumer<Cube>> subscription : new ArrayList<>(subscriptions.entrySet())) {
            CubePos pos = subscription.getKey();
            io.github.opencubicchunks.cubicchunks.core.server.chunkio.async.forge.AsyncWorldIOExecutor.dropQueuedCubeLoad(
                world, pos.getX(), pos.getY(), pos.getZ(), subscription.getValue());
        }
        subscriptions.clear();
        ended = System.nanoTime(); LabHooks.serverPackets = null;
        long[] gcEnd = LabData.gc();
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("schema", "cubiclab.server.v1"); data.put("runId", id); data.put("scenario", scenario);
        data.put("passed", failure == null); data.put("failure", failure); data.put("runtime", LabData.runtime());
        data.put("startUtc", startUtc); data.put("endUtc", Instant.now().toString());
        data.put("elapsedNanos", started == 0 ? 0 : ended - started); data.put("operations", operationCount);
        data.put("minY", minY); data.put("maxYExclusive", maxY); data.put("verticalCubesPerColumn", (maxY - minY) / 16);
        data.put("initialLoadedCubes", initialCubes); data.put("finalLoadedCubes", provider.getLoadedCubeCount());
        data.put("retainedFixtureCubes", held.size()); data.put("serverTicks", ticks.summary()); data.put("operationDurations", operations.summary());
        data.put("saveSubmissionNanos", submissionNanos); data.put("blockingFlushNanos", flushNanos);
        data.put("lookupChecksum", lookupChecksum); data.put("cubeLoadEvents", cubeLoads); data.put("cubeUnloadEvents", cubeUnloads);
        data.put("cubeDataLoadEvents", dataLoads); data.put("cubeDataSaveEvents", dataSaves); data.put("packets", packets.summary());
        data.put("participants", peers); data.put("horizontalViewDistance", server.getPlayerList().getViewDistance());
        data.put("verticalViewDistance", ((io.github.opencubicchunks.cubicchunks.core.server.ICubicPlayerList) server.getPlayerList()).getVerticalViewDistance());
        data.put("configuredClientVerticalViewDistance", CubicChunksConfig.verticalCubeLoadDistance);
        data.put("gcCollections", gcStart == null ? 0 : gcEnd[0] - gcStart[0]);
        data.put("gcReportedMillis", gcStart == null ? 0 : gcEnd[1] - gcStart[1]);
        data.put("notes", "Operation durations are synchronous calls or async request-to-callback latency. Resident durations cover batches of 10000 lookups. Flush explicitly blocks. Reload means a new JVM, not an OS disk-cache purge.");
        LabData.write(output.resolve("server.json"), data);
        for (EntityPlayerMP player : server.getPlayerList().getPlayers()) if (peers.contains(player.getUniqueID()))
            Network.CHANNEL.sendTo(new Network.ClientMessage(CubicLab.control("stop", id, scenario)), player);
        server.sendMessage(new TextComponentString("CUBICLAB_SERVER_RESULT runId=" + id + " scenario=" + scenario + " " + (failure == null ? "PASS" : "FAIL")));
    }
}

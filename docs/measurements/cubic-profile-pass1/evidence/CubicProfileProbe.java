package supersymmetry.riven.experiment;

import com.google.gson.GsonBuilder;
import io.github.opencubicchunks.cubicchunks.api.world.ICubeProviderServer.Requirement;
import io.github.opencubicchunks.cubicchunks.core.server.CubeProviderServer;
import io.github.opencubicchunks.cubicchunks.core.world.cube.Cube;
import net.minecraft.command.CommandBase;
import net.minecraft.command.CommandException;
import net.minecraft.command.ICommandSender;
import net.minecraft.server.MinecraftServer;
import net.minecraft.util.text.TextComponentString;

import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Deterministic server-thread diagnostic for disposable development worlds. */
final class CubicProfileProbe extends CommandBase {
    private static final int BATCHES = 3;
    private static final int LOOKUPS = 1_000_000;

    @Override public String getName() { return "riven_cubic_profile"; }
    @Override public String getUsage(ICommandSender sender) { return "riven_cubic_profile write|read cleanroom|forge [callbacks]"; }

    @Override public void execute(MinecraftServer server, ICommandSender sender, String[] args) throws CommandException {
        if (args.length < 2 || args.length > 3 || !(args[0].equals("write") || args[0].equals("read"))
                || !(args[1].equals("cleanroom") || args[1].equals("forge"))
                || (args.length == 3 && !args[2].equals("callbacks"))) throw new CommandException(getUsage(sender));
        Path output = Paths.get("cubic-profile-" + args[0] + ".json");
        if (Files.exists(output)) throw new CommandException("Profile evidence already exists");
        boolean write = args[0].equals("write");
        CubeProviderServer provider = (CubeProviderServer) server.getWorld(0).getChunkProvider();
        Map<String, Object> result = new LinkedHashMap<>();
        List<Map<String, Object>> phases = new ArrayList<>();
        result.put("schema", 1);
        result.put("mode", args[0]);
        result.put("loader", args[1]);
        result.put("phases", phases);
        result.put("passed", false);
        try {
            Cube witness = null;
            for (int batch = 0; batch < BATCHES; batch++) {
                Cube[] cubes = new Cube[512];
                Instant start = Instant.now();
                long before = System.nanoTime();
                int count = 0;
                long checksum = 0;
                for (int x = 128 + batch * 8; x < 132 + batch * 8; x++) {
                    for (int z = 128; z < 132; z++) for (int y = -8; y < 24; y++) {
                        if (provider.getLoadedCube(x, y, z) != null) throw new IllegalStateException("Expected uncached cube");
                        Cube cube = provider.getCubeNow(x, y, z, write ? Requirement.GENERATE : Requirement.LOAD);
                        if (cube == null || cube.getX() != x || cube.getY() != y || cube.getZ() != z) {
                            throw new IllegalStateException("Missing or wrong cube " + x + "," + y + "," + z);
                        }
                        cubes[count++] = cube;
                        checksum += x * 31L + y * 17L + z;
                    }
                }
                phases.add(phase(write ? "generate" : "load", batch, start, before, count, provider, checksum));
                witness = cubes[0];
                start = Instant.now();
                before = System.nanoTime();
                checksum = 0;
                for (int i = 0; i < LOOKUPS; i++) {
                    Cube expected = cubes[i & 511];
                    Cube found = provider.getLoadedCube(expected.getX(), expected.getY(), expected.getZ());
                    if (found != expected) throw new IllegalStateException("Resident lookup changed cube identity");
                    checksum += found.getY();
                }
                phases.add(phase("resident_lookup", batch, start, before, LOOKUPS, provider, checksum));
            }
            Instant start = Instant.now();
            long before = System.nanoTime();
            provider.saveChunks(true);
            phases.add(phase("save_submit", 0, start, before, provider.getLoadedCubeCount(), provider, 0));
            start = Instant.now();
            before = System.nanoTime();
            int pending = provider.getCubeIO().getPendingCubeCount();
            provider.getCubeIO().flush();
            phases.add(phase("save_flush", 0, start, before, pending, provider, 0));
            if (args.length == 3) {
                // Cached cubes must still complete requests for population and lighting.
                Cube complete = provider.getCubeNow(witness.getX(), witness.getY(), witness.getZ(), Requirement.LIGHT);
                int[] callbacks = {0};
                for (Requirement req : new Requirement[] {Requirement.POPULATE, Requirement.LIGHT}) {
                    provider.asyncGetCube(complete.getX(), complete.getY(), complete.getZ(), req, cube -> {
                        if (cube != complete) throw new IllegalStateException("Callback returned another cube");
                        callbacks[0]++;
                    });
                }
                if (callbacks[0] != 2) throw new IllegalStateException("Missing cached async callbacks: " + callbacks[0]);
                result.put("cachedAsyncCallbacks", callbacks[0]);
                result.put("snapshotArrays", io.github.opencubicchunks.cubicchunks.core.server.chunkio.CubicSnapshotProbe.verify(complete));
            }
            result.put("passed", true);
        } catch (Exception failure) {
            result.put("failure", failure.toString());
        }
        try (Writer writer = Files.newBufferedWriter(output, StandardCharsets.UTF_8)) {
            new GsonBuilder().setPrettyPrinting().create().toJson(result, writer);
        } catch (Exception failure) {
            throw new CommandException("RIVEN_CUBIC_PROFILE_FAIL output: " + failure);
        }
        if (!Boolean.TRUE.equals(result.get("passed"))) throw new CommandException("RIVEN_CUBIC_PROFILE_FAIL " + result.get("failure"));
        sender.sendMessage(new TextComponentString("RIVEN_CUBIC_PROFILE_RESULT mode=" + args[0] + " PASS"));
    }

    private static Map<String, Object> phase(String name, int iteration, Instant start, long before,
            int operations, CubeProviderServer provider, long checksum) {
        long elapsed = System.nanoTime() - before;
        Map<String, Object> phase = new LinkedHashMap<>();
        phase.put("name", name);
        phase.put("iteration", iteration);
        phase.put("startUtc", start.toString());
        phase.put("endUtc", Instant.now().toString());
        phase.put("elapsedNanos", elapsed);
        phase.put("operations", operations);
        phase.put("loadedCubes", provider.getLoadedCubeCount());
        phase.put("checksum", checksum);
        return phase;
    }
}

package io.github.opencubicchunks.cubicchunks.core.server.chunkio;

import io.github.opencubicchunks.cubicchunks.core.world.cube.Cube;
import net.minecraft.nbt.NBTTagCompound;
import net.minecraft.world.chunk.Chunk;
import net.minecraft.world.chunk.storage.ExtendedBlockStorage;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/** Server-thread fixture for disposable worlds; kept outside the CubicChunks production artifact. */
public final class CubicSnapshotProbe {
    private CubicSnapshotProbe() { }

    /** Returns explicit pass/skip evidence; callers run this after timed profile phases. */
    public static List<String> verify(Cube cube) {
        if (cube == null || cube.getStorage() == null) {
            throw new IllegalStateException("Snapshot probe requires a cube with initialized block storage");
        }
        Chunk column = cube.getColumn();
        ExtendedBlockStorage storage = cube.getStorage();
        NBTTagCompound columnNbt = IONbtWriter.write(column).getCompoundTag("Level");
        NBTTagCompound cubeNbt = IONbtWriter.write(cube).getCompoundTag("Level");
        NBTTagCompound section = cubeNbt.getTagList("Sections", 10).getCompoundTagAt(0);
        List<String> results = new ArrayList<>();

        verifyArray("columnBiomes", column.getBiomeArray(), columnNbt.getByteArray("Biomes"), results);
        byte[] cubeBiomes = cube.getBiomeArray();
        if (cubeBiomes == null) {
            results.add("cubeBiomes: SKIP (not initialized)");
        } else {
            verifyArray("cubeBiomes", cubeBiomes, cubeNbt.getByteArray("Biomes3D"), results);
        }
        verifyArray("blockLight", storage.getBlockLight().getData(), section.getByteArray("BlockLight"), results);
        if (cube.getWorld().provider.hasSkyLight()) {
            verifyArray("skyLight", storage.getSkyLight().getData(), section.getByteArray("SkyLight"), results);
        } else {
            results.add("skyLight: SKIP (dimension has no skylight)");
        }
        return results;
    }

    private static void verifyArray(String name, byte[] live, byte[] snapshot, List<String> results) {
        byte[] original = live.clone();
        if (live.length == 0 || !Arrays.equals(original, snapshot)) {
            throw new IllegalStateException("Invalid initial " + name + " snapshot");
        }
        try {
            for (int i = 0; i < live.length; i++) live[i] ^= (byte) 0xff;
            if (!Arrays.equals(original, snapshot)) {
                throw new IllegalStateException("Queued " + name + " snapshot changed with live world data");
            }
            if (snapshot == live) throw new IllegalStateException("Queued " + name + " snapshot aliases live world data");
        } finally {
            System.arraycopy(original, 0, live, 0, original.length);
        }
        if (!Arrays.equals(original, live)) throw new IllegalStateException("Could not restore " + name + " fixture");
        results.add(name + ": PASS (" + live.length + " bytes)");
    }
}

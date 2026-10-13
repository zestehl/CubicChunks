import io.github.opencubicchunks.cubicchunks.api.util.CubePos;
import io.github.opencubicchunks.cubicchunks.api.world.storage.ICubicStorage;
import io.github.opencubicchunks.cubicchunks.core.lighting.phosphor.PooledLightUpdateQueue;
import io.github.opencubicchunks.cubicchunks.core.util.world.CubeSplitTickList;
import io.github.opencubicchunks.cubicchunks.core.util.world.CubeSplitTickSet;
import io.github.opencubicchunks.cubicchunks.core.world.ServerHeightMap;
import net.minecraft.nbt.NBTTagCompound;
import net.minecraft.nbt.NBTTagIntArray;
import net.minecraft.util.math.BlockPos;
import net.minecraft.util.math.ChunkPos;
import net.minecraft.world.NextTickListEntry;

import java.util.Arrays;
import java.util.Collections;
import java.util.Iterator;

/** Isolated observations of existing classes. No world, coremod or graphical client is started. */
public final class JavaOpportunityProbe {
    // Container contracts do not depend on registered blocks. Identity equality avoids block bootstrap.
    private static final class Entry extends NextTickListEntry {
        Entry(int x) { super(new BlockPos(x, 0, 0), null); }
        @Override public int hashCode() { return System.identityHashCode(this); }
        @Override public boolean equals(Object other) { return this == other; }
    }
    private interface Action { void run() throws Exception; }
    private static void observe(String name, Action action) {
        try { action.run(); System.out.println(name + "=completed"); }
        catch (Exception failure) { System.out.println(name + "=" + failure.getClass().getName()); }
    }
    private static CubeSplitTickSet tickSet() {
        CubeSplitTickSet result = new CubeSplitTickSet(); result.add(new Entry(0)); return result;
    }
    public static void main(String[] args) throws Exception {
        System.out.println("javaVersion=" + System.getProperty("java.version"));
        observe("scheduledSetClear", () -> tickSet().clear());
        observe("scheduledSetIteratorRemove", () -> {
            Iterator<NextTickListEntry> iterator = tickSet().iterator(); iterator.next(); iterator.remove();
        });
        CubeSplitTickList list = new CubeSplitTickList(); Entry old = new Entry(0), replacement = new Entry(1);
        list.add(old);
        System.out.println("scheduledListSetReturnsPrevious=" + (list.set(0, replacement) == old));
        System.out.println("scheduledListReplacementStored=" + (list.get(0) == replacement));

        ICubicStorage missing = new ICubicStorage() {
            public boolean columnExists(ChunkPos pos) { return false; }
            public boolean cubeExists(CubePos pos) { return false; }
            public NBTTagCompound readColumn(ChunkPos pos) { return null; }
            public NBTTagCompound readCube(CubePos pos) { return null; }
            public void writeColumn(ChunkPos pos, NBTTagCompound nbt) { }
            public void writeCube(CubePos pos, NBTTagCompound nbt) { }
            public void forEachColumn(java.util.function.Consumer<ChunkPos> consumer) { }
            public void forEachCube(java.util.function.Consumer<CubePos> consumer) { }
            public void flush() { }
            public void close() { }
        };
        observe("batchReadMissingColumn", () -> missing.readBatch(new ICubicStorage.PosBatch(
                Collections.singleton(new ChunkPos(0, 0)), Collections.emptySet())));
        observe("batchReadMissingCube", () -> missing.readBatch(new ICubicStorage.PosBatch(
                Collections.emptySet(), Collections.singleton(new CubePos(0, 0, 0)))));

        PooledLightUpdateQueue queue = new PooledLightUpdateQueue(new PooledLightUpdateQueue.Pool());
        System.out.println("newLightingQueueSize=" + queue.size());
        System.out.println("newLightingQueueEmpty=" + queue.isEmpty());

        int[] liveHeightmap = new int[] {80}; NBTTagIntArray tag = new NBTTagIntArray(liveHeightmap);
        liveHeightmap[0] = 384;
        System.out.println("nbtIntArrayRetainsInput=" + (tag.getIntArray()[0] == 384));
        NBTTagCompound compound = new NBTTagCompound(); int[] compoundHeightmap = new int[] {80};
        compound.setIntArray("LastHeightMap", compoundHeightmap); compoundHeightmap[0] = 384;
        System.out.println("nbtCompoundIntArrayRetainsInput=" + (compound.getIntArray("LastHeightMap")[0] == 384));

        ServerHeightMap map = new ServerHeightMap(new int[256]);
        map.onOpacityChange(0, 0, 0, 255); map.onOpacityChange(0, 4, 0, 255);
        byte[] empty = new ServerHeightMap(new int[256]).getData();
        map.readData(empty);
        System.out.println("heightmapReuseMatchesEmptyPayload=" + Arrays.equals(empty, map.getData()));
        System.out.println("heightmapEmptyPayloadBytes=" + empty.length);
        System.out.println("heightmapReusedPayloadBytes=" + map.getData().length);

        ServerHeightMap cached = new ServerHeightMap(new int[256]);
        for (int z = 0; z < 16; z++) for (int x = 0; x < 16; x++) cached.onOpacityChange(x, 32, z, 255);
        int before = cached.getLowestTopBlockY(); cached.readData(empty);
        System.out.println("heightmapLowestCacheAfterRead=" + cached.getLowestTopBlockY());
        System.out.println("heightmapLowestCacheBeforeRead=" + before);
    }
}

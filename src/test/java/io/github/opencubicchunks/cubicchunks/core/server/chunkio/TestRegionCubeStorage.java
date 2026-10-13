package io.github.opencubicchunks.cubicchunks.core.server.chunkio;

import io.github.opencubicchunks.cubicchunks.api.util.CubePos;
import io.github.opencubicchunks.cubicchunks.api.world.storage.ICubicStorage;
import io.netty.buffer.ByteBuf;
import net.minecraft.nbt.NBTTagCompound;
import net.minecraft.util.math.ChunkPos;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;
import java.io.IOException;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import static org.junit.Assert.*;

public class TestRegionCubeStorage {
    @Rule public final TemporaryFolder temporary = new TemporaryFolder();
    @Test public void compressionFailureReleasesEarlierBuffersAndWritesNothing() throws Exception {
        try (TrackedStore storage = new TrackedStore(temporary.newFolder().toPath())) {
            storage.failAt = 3;
            Map<CubePos, NBTTagCompound> cubes = new LinkedHashMap<>();
            for (int i = 0; i < 4; i++) cubes.put(new CubePos(0, i - 8, 0), TestPendingCubeWrites.tag(i));
            try { storage.writeBatch(new ICubicStorage.NBTBatch(Collections.singletonMap(new ChunkPos(0, 0), TestPendingCubeWrites.tag(1)), cubes)); fail(); }
            catch (IOException expected) { assertEquals("compression failed", expected.getMessage()); }
            assertEquals(2, storage.buffers.size());
            storage.buffers.forEach(buffer -> assertEquals(0, buffer.refCnt()));
            assertNull(storage.readColumn(new ChunkPos(0, 0))); assertNull(storage.readCube(new CubePos(0, -8, 0)));
        }
    }
    @Test public void successfulWritesReleaseBuffersAndRoundTripAfterClose() throws Exception {
        Path path = temporary.newFolder().toPath(); CubePos cube = new CubePos(-1, 23, 0); ChunkPos column = new ChunkPos(-1, 0);
        NBTTagCompound original = TestPendingCubeWrites.tag(42); original.setByteArray("data", new byte[] {0, 1, 2});
        try (TrackedStore storage = new TrackedStore(path)) {
            storage.writeBatch(new ICubicStorage.NBTBatch(Collections.singletonMap(column, original), Collections.singletonMap(cube, original)));
            storage.flush(); storage.buffers.forEach(buffer -> assertEquals(0, buffer.refCnt()));
        }
        try (RegionCubeStorage reopened = new RegionCubeStorage(path)) {
            assertEquals(original, reopened.readColumn(column)); assertEquals(original, reopened.readCube(cube));
            assertFalse(reopened.cubeExists(new CubePos(-1, -8, 0)));
        }
    }
    @Test public void runtimeKeyMappingFailureReleasesEarlierBuffers() throws Exception {
        try (TrackedStore storage = new TrackedStore(temporary.newFolder().toPath())) {
            Map<Integer, NBTTagCompound> values = new LinkedHashMap<>(); values.put(0, TestPendingCubeWrites.tag(0)); values.put(1, TestPendingCubeWrites.tag(1));
            try { storage.compressNBTForBatchWrite(values, key -> { if (key == 1) throw new IllegalArgumentException("key failed"); return key; }); fail(); }
            catch (IllegalArgumentException expected) { }
            assertEquals(1, storage.buffers.size()); assertEquals(0, storage.buffers.get(0).refCnt());
        }
    }
    private static class TrackedStore extends RegionCubeStorage {
        final List<ByteBuf> buffers = new ArrayList<>(); int calls, failAt = -1;
        TrackedStore(Path path) throws IOException { super(path); }
        @Override protected ByteBuf compressNBT(NBTTagCompound nbt) throws IOException {
            if (++calls == failAt) throw new IOException("compression failed");
            ByteBuf buffer = super.compressNBT(nbt); buffers.add(buffer); return buffer;
        }
    }
}

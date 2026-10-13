package io.github.opencubicchunks.cubicchunks.core.server.chunkio;

import io.github.opencubicchunks.cubicchunks.api.util.CubePos;
import io.github.opencubicchunks.cubicchunks.api.world.storage.ICubicStorage;
import net.minecraft.nbt.NBTTagCompound;
import net.minecraft.util.math.ChunkPos;
import org.junit.After;
import org.junit.Test;

import java.io.IOException;
import java.io.InterruptedIOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;

import static org.junit.Assert.*;

public class TestPendingCubeWrites {
    private final List<PendingCubeWrites> queues = new ArrayList<>();
    @After public void stop() { queues.forEach(PendingCubeWrites::stop); Thread.interrupted(); }
    private PendingCubeWrites queue(Store storage, int columns, int cubes) {
        PendingCubeWrites queue = new PendingCubeWrites(storage, columns, cubes, error -> storage.reports++);
        queues.add(queue);
        return queue;
    }
    static NBTTagCompound tag(int value) { NBTTagCompound nbt = new NBTTagCompound(); nbt.setInteger("value", value); return nbt; }
    private static CubePos cube(int x) { return new CubePos(x, -8, 0); }

    @Test public void batchesAreBoundedAndDoNotStarveEitherKind() throws Exception {
        Store storage = new Store(); PendingCubeWrites queue = queue(storage, 2, 3);
        for (int i = 0; i < 7; i++) { queue.putCube(cube(i), tag(i)); queue.putColumn(new ChunkPos(i, 0), tag(i)); }
        assertTrue(queue.writeNext());
        assertEquals(2, storage.lastColumns); assertEquals(3, storage.lastCubes);
        queue.flush();
        assertEquals(7, storage.cubes.size()); assertEquals(7, storage.columns.size());
        assertFalse(queue.hasPending()); assertEquals(1, storage.flushes);
    }

    @Test public void failedBatchesAreRetainedWithoutAutomaticRetry() throws Exception {
        Store storage = new Store(); PendingCubeWrites queue = queue(storage, 1, 2);
        queue.putCube(cube(0), tag(10)); storage.fail = true;
        assertFalse(queue.writeNext());
        for (int i = 0; i < 100; i++) { assertFalse(queue.writeNext()); queue.signal(); }
        assertEquals(1, storage.attempts); assertEquals(1, storage.reports);
        assertEquals(10, queue.readCube(cube(0)).getInteger("value"));
        queue.putCube(cube(0), tag(11));
        try { queue.flush(); fail("Explicit retry must report the persistent failure"); } catch (IOException expected) { }
        assertEquals(2, storage.attempts); assertTrue(queue.hasPending());
        storage.fail = false; queue.flush();
        assertEquals(11, storage.cubes.get(cube(0)).getInteger("value")); assertFalse(queue.hasFailure());
    }

    @Test public void newerEqualSnapshotSurvivesAnOlderWrite() throws Exception {
        Store storage = new Store(); PendingCubeWrites queue = queue(storage, 1, 1);
        NBTTagCompound first = tag(1); queue.putCube(cube(0), first);
        storage.duringWrite = batch -> { storage.duringWrite = null; queue.putCube(cube(0), first.copy()); };
        assertTrue(queue.writeNext()); assertTrue(queue.hasPending());
        queue.flush(); assertEquals(2, storage.attempts); assertFalse(queue.hasPending());
    }

    @Test public void continuallyReplacedSnapshotYieldsToOlderCoordinates() throws Exception {
        Store storage = new Store(); PendingCubeWrites queue = queue(storage, 1, 1);
        queue.putCube(cube(0), tag(0)); queue.putCube(cube(1), tag(1));
        storage.duringWrite = batch -> queue.putCube(cube(0), tag(2));
        queue.writeNext(); queue.writeNext();
        assertEquals(1, storage.cubes.get(cube(1)).getInteger("value"));
        storage.duringWrite = null; queue.flush();
    }

    @Test public void pendingReadersCannotMutateQueuedSnapshots() {
        Store storage = new Store(); PendingCubeWrites queue = queue(storage, 1, 1);
        NBTTagCompound source = tag(7); source.setByteArray("bytes", new byte[] {1, 2});
        queue.putCube(cube(0), source); queue.putColumn(new ChunkPos(0, 0), source);
        NBTTagCompound copy = queue.readCube(cube(0)); copy.setInteger("value", 8); copy.getByteArray("bytes")[0] = 9;
        queue.readColumn(new ChunkPos(0, 0)).setInteger("value", 9);
        assertEquals(7, queue.readCube(cube(0)).getInteger("value"));
        assertArrayEquals(new byte[] {1, 2}, queue.readCube(cube(0)).getByteArray("bytes"));
        assertEquals(7, queue.readColumn(new ChunkPos(0, 0)).getInteger("value"));
    }

    @Test public void interruptedFlushRetainsWorkAndRestoresInterruptStatus() throws Exception {
        Store storage = new Store(); PendingCubeWrites queue = queue(storage, 1, 1); queue.putCube(cube(0), tag(1));
        Thread.currentThread().interrupt();
        try { queue.flush(); fail("Must report interruption"); } catch (InterruptedIOException expected) { }
        assertTrue(Thread.currentThread().isInterrupted()); assertEquals(0, storage.attempts); assertTrue(queue.hasPending());
        Thread.interrupted(); queue.flush(); assertFalse(queue.hasPending());
    }

    @Test public void backendFlushFailureIsReportedAndRetryable() throws Exception {
        Store storage = new Store(); PendingCubeWrites queue = queue(storage, 1, 1);
        queue.putCube(cube(0), tag(1)); storage.failFlush = true;
        try { queue.flush(); fail("Must report force failure"); } catch (IOException expected) { }
        assertTrue(queue.hasFailure()); assertEquals(1, storage.cubes.size());
        storage.failFlush = false; queue.flush(); assertFalse(queue.hasFailure());
    }

    @Test public void uncheckedBackendFailureAlsoRetainsTheBatch() throws Exception {
        Store storage = new Store(); PendingCubeWrites queue = queue(storage, 1, 1); queue.putCube(cube(0), tag(1));
        storage.duringWrite = batch -> { throw new IllegalStateException("injected"); };
        assertFalse(queue.writeNext()); assertTrue(queue.hasFailure()); assertTrue(queue.hasPending());
        storage.duringWrite = null; queue.flush(); assertFalse(queue.hasPending());
    }

    @Test public void publicationsDuringWorkerCompletionAreNotStranded() throws Exception {
        Store storage = new Store(); PendingCubeWrites queue = queue(storage, 2, 4);
        CountDownLatch firstWrite = new CountDownLatch(1); CountDownLatch release = new CountDownLatch(1);
        storage.duringWrite = batch -> {
            storage.duringWrite = null; firstWrite.countDown();
            try { assertTrue(release.await(5, TimeUnit.SECONDS)); } catch (InterruptedException e) { throw new AssertionError(e); }
        };
        queue.putCube(cube(0), tag(0)); queue.signal(); assertTrue(firstWrite.await(5, TimeUnit.SECONDS));
        for (int i = 1; i < 200; i++) { queue.putCube(cube(i), tag(i)); queue.signal(); }
        release.countDown();
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5);
        while (queue.hasPending() && System.nanoTime() < deadline) Thread.yield();
        assertFalse("Worker must consume every publication without a flush rescue", queue.hasPending());
        queue.flush(); assertEquals(200, storage.cubes.size());
    }

    @Test public void missingBatchReadsRetainAllRequestedKeysAndNulls() throws Exception {
        Store storage = new Store(); storage.cubes.put(cube(1), tag(1));
        ICubicStorage.NBTBatch batch = storage.readBatch(new ICubicStorage.PosBatch(
                Collections.singleton(new ChunkPos(0, 0)), new HashSet<>(java.util.Arrays.asList(cube(0), cube(1)))));
        assertTrue(batch.columns.containsKey(new ChunkPos(0, 0))); assertNull(batch.columns.get(new ChunkPos(0, 0)));
        assertEquals(2, batch.cubes.size()); assertNull(batch.cubes.get(cube(0)));
        assertEquals(1, batch.cubes.get(cube(1)).getInteger("value"));
    }

    @Test public void batchReadPropagatesTheActualIoFailure() throws Exception {
        Store storage = new Store() { @Override public NBTTagCompound readCube(CubePos pos) throws IOException { throw new IOException("read failed"); } };
        try { storage.readBatch(new ICubicStorage.PosBatch(Collections.emptySet(), Collections.singleton(cube(0)))); fail(); }
        catch (IOException expected) { assertEquals("read failed", expected.getMessage()); }
    }

    static class Store implements ICubicStorage {
        final Map<ChunkPos, NBTTagCompound> columns = new HashMap<>();
        final Map<CubePos, NBTTagCompound> cubes = new HashMap<>();
        int attempts, reports, lastColumns, lastCubes, flushes;
        boolean fail, failFlush;
        volatile Consumer<NBTBatch> duringWrite;
        public boolean columnExists(ChunkPos pos) { return columns.containsKey(pos); }
        public boolean cubeExists(CubePos pos) { return cubes.containsKey(pos); }
        public NBTTagCompound readColumn(ChunkPos pos) throws IOException { return columns.get(pos); }
        public NBTTagCompound readCube(CubePos pos) throws IOException { return cubes.get(pos); }
        public void writeColumn(ChunkPos pos, NBTTagCompound nbt) { columns.put(pos, nbt.copy()); }
        public void writeCube(CubePos pos, NBTTagCompound nbt) { cubes.put(pos, nbt.copy()); }
        public void writeBatch(NBTBatch batch) throws IOException {
            attempts++; lastColumns = batch.columns.size(); lastCubes = batch.cubes.size();
            if (duringWrite != null) duringWrite.accept(batch);
            if (fail) throw new IOException("injected write failure");
            batch.columns.forEach(this::writeColumn); batch.cubes.forEach(this::writeCube);
        }
        public void forEachColumn(Consumer<ChunkPos> callback) { columns.keySet().forEach(callback); }
        public void forEachCube(Consumer<CubePos> callback) { cubes.keySet().forEach(callback); }
        public void flush() throws IOException { flushes++; if (failFlush) throw new IOException("injected force failure"); }
        public void close() { }
    }
}

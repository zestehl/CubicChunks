package io.github.opencubicchunks.cubicchunks.lab;
import org.junit.Test;
import static org.junit.Assert.*;
public class TestSamples {
    @Test public void emptyDurationsAreUnknown() { assertNull(new Samples().summary().get("p95Ms")); }
    @Test public void nearestRankPreservesTailStalls() {
        Samples samples = new Samples(); for (int i = 1; i <= 100; i++) samples.add(i * 1000000L);
        assertEquals(95.0, (Double) samples.summary().get("p95Ms"), 0);
        assertEquals(99.0, (Double) samples.summary().get("p99Ms"), 0);
        assertEquals(50.5, (Double) samples.summary().get("meanMs"), 0);
    }
    @Test public void boundedStorageStillCountsDroppedObservations() {
        Samples samples = new Samples(); for (int i = 0; i < 120010; i++) samples.add(1);
        assertEquals(10L, samples.summary().get("droppedCount")); assertEquals(120010L, samples.summary().get("count"));
    }
    @Test public void verticalRouteCoversEveryAllocatedCubeAtViewDistanceThree() {
        java.util.Set<Integer> covered = new java.util.HashSet<>();
        for (int step = 0; step <= 5; step++) {
            double y = LabRoute.height(-128, 384, step);
            assertTrue(y >= -128 && y < 384);
            int cubeY = ((int) Math.floor(y)) >> 4;
            for (int offset = -3; offset <= 3; offset++) covered.add(cubeY + offset);
        }
        for (int cubeY = -8; cubeY < 24; cubeY++) assertTrue("Unvisited cube layer " + cubeY, covered.contains(cubeY));
        assertEquals(376.0, LabRoute.height(-128, 384, 5), 0);
    }
}

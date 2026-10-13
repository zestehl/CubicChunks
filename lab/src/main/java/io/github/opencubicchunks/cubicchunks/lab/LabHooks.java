package io.github.opencubicchunks.cubicchunks.lab;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;

/** Packet counters are safe on Netty threads; world state never moves into these hooks. */
public final class LabHooks {
    public static volatile PacketCounters serverPackets, clientPackets;
    public static final ThreadLocal<Invocation> encode = new ThreadLocal<>(), decode = new ThreadLocal<>(), apply = new ThreadLocal<>();
    public static final class Invocation {
        public final PacketCounters counters;
        public final long started = System.nanoTime();
        public final int index, cubes;
        public Invocation(PacketCounters counters, int index, int cubes) { this.counters = counters; this.index = index; this.cubes = cubes; }
    }
    public static final class PacketCounters {
        public final AtomicLong count = new AtomicLong(), bytes = new AtomicLong(), cubes = new AtomicLong(), nanos = new AtomicLong();
        public final AtomicLong applyCount = new AtomicLong(), applyNanos = new AtomicLong();
        public void record(long duration, int size, int cubeCount) {
            count.incrementAndGet(); bytes.addAndGet(size); cubes.addAndGet(cubeCount); nanos.addAndGet(duration);
        }
        public Map<String, Object> summary() {
            Map<String, Object> data = new LinkedHashMap<>();
            data.put("packetCount", count.get()); data.put("serializedPayloadBytes", bytes.get());
            data.put("cubeCount", cubes.get()); data.put("serializationNanos", nanos.get());
            data.put("applyCount", applyCount.get()); data.put("applyNanos", applyNanos.get());
            data.put("byteScope", "PacketCubes payload before transport compression, excludes channel framing");
            return data;
        }
    }
}

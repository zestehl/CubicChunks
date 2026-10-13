package io.github.opencubicchunks.cubicchunks.lab;

import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.Map;

/** Bounded duration observations; dropped observations are reported instead of hidden. */
public final class Samples {
    private final long[] values = new long[120000];
    private int size;
    private long totalCount, totalNs, maximumNs;
    public void add(long ns) {
        if (ns < 0) throw new IllegalArgumentException("Negative duration");
        totalCount++; totalNs += ns; maximumNs = Math.max(maximumNs, ns);
        if (size < values.length) values[size++] = ns;
    }
    public Map<String, Object> summary() {
        long[] sorted = Arrays.copyOf(values, size);
        Arrays.sort(sorted);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("count", totalCount); result.put("storedCount", size);
        result.put("droppedCount", totalCount - size); result.put("totalNanos", totalNs);
        result.put("meanMs", totalCount == 0 ? null : totalNs / 1e6 / totalCount);
        result.put("p50Ms", percentile(sorted, .50)); result.put("p95Ms", percentile(sorted, .95));
        result.put("p99Ms", percentile(sorted, .99)); result.put("maxMs", totalCount == 0 ? null : maximumNs / 1e6);
        return result;
    }
    static Double percentile(long[] sorted, double quantile) {
        return sorted.length == 0 ? null : sorted[(int) Math.ceil(quantile * sorted.length) - 1] / 1e6;
    }
}

package io.github.opencubicchunks.cubicchunks.lab;

import com.google.gson.GsonBuilder;
import java.io.IOException;
import java.io.Writer;
import java.lang.management.GarbageCollectorMXBean;
import java.lang.management.ManagementFactory;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

public final class LabData {
    private LabData() { }
    public static void write(Path path, Object value) {
        try {
            Files.createDirectories(path.getParent());
            try (Writer writer = Files.newBufferedWriter(path, StandardCharsets.UTF_8,
                    StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)) {
                new GsonBuilder().setPrettyPrinting().create().toJson(value, writer);
            }
        } catch (IOException error) { throw new IllegalStateException("Cannot preserve lab result " + path, error); }
    }
    public static long[] gc() {
        long count = 0, milliseconds = 0;
        for (GarbageCollectorMXBean bean : ManagementFactory.getGarbageCollectorMXBeans()) {
            count += Math.max(0, bean.getCollectionCount()); milliseconds += Math.max(0, bean.getCollectionTime());
        }
        return new long[] {count, milliseconds};
    }
    public static Map<String, Object> runtime() {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("java", System.getProperty("java.version")); result.put("os", System.getProperty("os.name"));
        result.put("arch", System.getProperty("os.arch")); result.put("processors", Runtime.getRuntime().availableProcessors());
        result.put("maxHeapBytes", Runtime.getRuntime().maxMemory());
        return result;
    }
}

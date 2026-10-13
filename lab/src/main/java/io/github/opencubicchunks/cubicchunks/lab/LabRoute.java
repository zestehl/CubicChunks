package io.github.opencubicchunks.cubicchunks.lab;
public final class LabRoute {
    private LabRoute() { }
    public static double height(int minY, int maxYExclusive, int step) {
        if (step < 0 || step > 5 || maxYExclusive - (long) minY < 16) throw new IllegalArgumentException("Invalid route");
        return minY + 8 + (maxYExclusive - (long) minY - 16) * step / 5.0;
    }
}

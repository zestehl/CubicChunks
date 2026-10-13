package supersymmetry.riven.tools;

import supersymmetry.riven.model.preparation.PreparationSession;
import supersymmetry.riven.model.preparation.SessionPreparationCache;

/** Synthetic request orders against the selected Riven binary's real cache; no world or cost benchmark. */
public final class RivenAreaCacheDiagnostic {
    public static void main(String[] args) {
        int distance = args.length == 0 ? 12 : Integer.parseInt(args[0]);
        if (distance < 2 || distance > 32) throw new IllegalArgumentException("Invalid view distance");
        int levels = distance * 2 + 1, areas = levels * levels;
        System.out.println("view_distance,capacity,pattern,distinct_chunk_areas,cube_levels,requests,area_preparations,cache_hits,retained_areas");
        for (int capacity : new int[] {8, 16, 32, areas / 2, areas, areas * 2}) {
            for (int pattern = 0; pattern < 3; pattern++) {
                PreparationSession session = new PreparationSession();
                SessionPreparationCache<Integer, Integer> cache = new SessionPreparationCache<>(capacity, 8, value -> 1);
                int requests = 0;
                if (pattern != 2) {
                    for (int area = 0; area < areas; area++) { get(cache, session, area); requests++; }
                }
                if (pattern == 0) {
                    for (int level = 0; level < levels; level++) for (int area = 0; area < areas; area++) {
                        get(cache, session, area); requests++;
                    }
                } else {
                    for (int area = 0; area < areas; area++) {
                        if (pattern == 2) { get(cache, session, area); requests++; }
                        for (int level = 0; level < levels; level++) { get(cache, session, area); requests++; }
                    }
                }
                String name = new String[] {"columns_then_level_sweeps", "columns_then_column_groups", "column_then_its_cubes"}[pattern];
                System.out.println(distance + "," + capacity + "," + name + "," + areas + "," + levels + "," + requests + "," + cache.preparedCount()
                        + "," + (requests - cache.preparedCount()) + "," + cache.size());
                session.close(); cache.invalidate(session);
            }
        }
    }
    private static void get(SessionPreparationCache<Integer, Integer> cache, PreparationSession session, int area) {
        if (cache.get(session, area, () -> area).intValue() != area) throw new AssertionError("Wrong prepared coordinate");
    }
}

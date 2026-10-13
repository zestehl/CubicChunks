package io.github.opencubicchunks.cubicchunks.lab;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import io.github.opencubicchunks.cubicchunks.api.world.CubeEvent;
import net.minecraft.client.Minecraft;
import net.minecraft.util.ScreenShotHelper;
import net.minecraftforge.client.event.RenderGameOverlayEvent;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.fml.common.eventhandler.SubscribeEvent;
import net.minecraftforge.fml.common.gameevent.TickEvent;
import org.lwjgl.opengl.GL11;
import java.time.Instant;
import java.util.*;

/** Only loaded on a real client. Reports frame pacing separately from render-event work. */
public final class ClientProxy extends CommonProxy {
    private Capture active;
    private JsonObject pending;
    private String last = "Ready: /cubiclab run vertical";
    private String lastScreen;
    public void initialize() { MinecraftForge.EVENT_BUS.register(this); }
    public void clientMessage(String message) {
        Minecraft.getMinecraft().addScheduledTask(() -> {
            JsonObject data = new JsonParser().parse(message).getAsJsonObject();
            String op = data.get("op").getAsString();
            if (op.equals("start")) pending = data;
            if (op.equals("stop") && active != null && active.id.equals(data.get("runId").getAsString())) finish();
            if (op.equals("quit")) Minecraft.getMinecraft().shutdown();
        });
    }
    @SubscribeEvent public void clientTick(TickEvent.ClientTickEvent event) {
        Minecraft mc = Minecraft.getMinecraft();
        if (event.phase == TickEvent.Phase.END && mc.world != null && mc.player != null) {
            String screen = mc.currentScreen == null ? "none" : mc.currentScreen.getClass().getName();
            if (!screen.equals(lastScreen)) { lastScreen = screen; System.out.println("CUBICLAB_CLIENT_VIEW screen=" + screen); }
        }
        if (event.phase == TickEvent.Phase.END && pending != null && mc.world != null && mc.player != null && mc.currentScreen == null) {
            active = new Capture(pending); pending = null; LabHooks.clientPackets = active.packets;
            Network.CHANNEL.sendToServer(new Network.ServerMessage(CubicLab.control("ready", active.id, active.scenario)));
        }
        if (active == null) return;
        if (event.phase == TickEvent.Phase.START) active.tickStarted = System.nanoTime();
        else if (active.tickStarted != 0) { active.ticks.add(System.nanoTime() - active.tickStarted); active.tickStarted = 0; }
    }
    @SubscribeEvent public void render(TickEvent.RenderTickEvent event) {
        if (active == null) return;
        long now = System.nanoTime();
        if (event.phase == TickEvent.Phase.START) {
            if (active.lastFrame != 0) active.frames.add(now - active.lastFrame);
            active.lastFrame = now; active.renderStarted = now;
            if (Minecraft.getMinecraft().currentScreen != null) active.guiFrames++;
        } else if (active.renderStarted != 0) { active.render.add(now - active.renderStarted); active.renderStarted = 0; }
    }
    @SubscribeEvent public void load(CubeEvent.Load event) {
        if (active != null && event.getWorld().isRemote) {
            active.loads++; int y = event.getCube().getY();
            active.loadedByY.put(y, active.loadedByY.getOrDefault(y, 0L) + 1);
            io.github.opencubicchunks.cubicchunks.api.world.ICubicWorld world = (io.github.opencubicchunks.cubicchunks.api.world.ICubicWorld) event.getWorld();
            if (y < (world.getMinHeight() >> 4) || y >= (world.getMaxHeight() >> 4)) active.outsideHeightLoads++;
        }
    }
    @SubscribeEvent public void unload(CubeEvent.Unload event) { if (active != null && event.getWorld().isRemote) active.unloads++; }
    @SubscribeEvent public void overlay(RenderGameOverlayEvent.Text event) {
        event.getLeft().add("Cubic Lab: " + (active == null ? last : active.scenario + " / " + active.id.substring(0, 8)));
        if (active != null) event.getLeft().add("Received cubes: " + active.packets.cubes.get() + " / " + active.packets.bytes.get() / 1024 + " KiB payload");
    }
    private void finish() {
        Minecraft mc = Minecraft.getMinecraft(); Capture capture = active; active = null; LabHooks.clientPackets = null;
        long[] gc = LabData.gc();
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("schema", "cubiclab.client.v1"); result.put("runId", capture.id); result.put("scenario", capture.scenario);
        result.put("runtime", LabData.runtime()); result.put("startUtc", capture.startUtc); result.put("endUtc", Instant.now().toString());
        result.put("elapsedNanos", System.nanoTime() - capture.started); result.put("frameIntervals", capture.frames.summary());
        result.put("renderEventWork", capture.render.summary()); result.put("clientTicks", capture.ticks.summary());
        result.put("packets", capture.packets.summary()); result.put("cubeLoadEvents", capture.loads);
        result.put("cubeUnloadEvents", capture.unloads); result.put("observedLoadsByCubeY", capture.loadedByY);
        result.put("loadsOutsideBuildHeight", capture.outsideHeightLoads);
        result.put("framesWithGui", capture.guiFrames); result.put("renderDistance", mc.gameSettings.renderDistanceChunks);
        result.put("verticalViewDistance", io.github.opencubicchunks.cubicchunks.core.CubicChunksConfig.verticalCubeLoadDistance);
        result.put("frameCap", mc.gameSettings.limitFramerate); result.put("vsync", mc.gameSettings.enableVsync);
        result.put("fancyGraphics", mc.gameSettings.fancyGraphics); result.put("fullscreen", mc.gameSettings.fullScreen);
        result.put("width", mc.displayWidth); result.put("height", mc.displayHeight);
        result.put("glVendor", GL11.glGetString(GL11.GL_VENDOR)); result.put("glRenderer", GL11.glGetString(GL11.GL_RENDERER));
        result.put("glVersion", GL11.glGetString(GL11.GL_VERSION));
        result.put("gcCollections", gc[0] - capture.gc[0]); result.put("gcReportedMillis", gc[1] - capture.gc[1]);
        result.put("notes", "Frame intervals include cap/vsync/scheduling. Render-event work is not exclusive GPU time. Packet decode runs on network threads; apply measures main-thread cube/block/light/entity handling. Phase window includes control-message latency.");
        LabData.write(mc.gameDir.toPath().resolve("cubiclab-results").resolve(capture.id).resolve("client.json"), result);
        JsonObject report = new com.google.gson.Gson().toJsonTree(result).getAsJsonObject(); report.addProperty("op", "report");
        Network.CHANNEL.sendToServer(new Network.ServerMessage(report));
        last = capture.scenario + " finished; results saved";
        // Capture real rendered output after measurement so the screenshot cost is excluded.
        ScreenShotHelper.saveScreenshot(mc.gameDir, "cubiclab-" + capture.id + ".png", mc.displayWidth, mc.displayHeight, mc.getFramebuffer());
        System.out.println("CUBICLAB_CLIENT_SAVED runId=" + capture.id);
    }
    private static final class Capture {
        final String id, scenario, startUtc = Instant.now().toString();
        final long started = System.nanoTime();
        final long[] gc = LabData.gc();
        final Samples frames = new Samples(), ticks = new Samples(), render = new Samples();
        final LabHooks.PacketCounters packets = new LabHooks.PacketCounters();
        final Map<Integer, Long> loadedByY = new TreeMap<>();
        long tickStarted, renderStarted, lastFrame, loads, unloads, guiFrames, outsideHeightLoads;
        Capture(JsonObject data) { id = data.get("runId").getAsString(); scenario = data.get("scenario").getAsString(); }
    }
}

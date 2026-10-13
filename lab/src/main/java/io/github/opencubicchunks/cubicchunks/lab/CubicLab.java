package io.github.opencubicchunks.cubicchunks.lab;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import io.github.opencubicchunks.cubicchunks.api.world.CubeEvent;
import io.github.opencubicchunks.cubicchunks.api.world.CubeDataEvent;
import net.minecraft.command.*;
import net.minecraft.entity.player.EntityPlayerMP;
import net.minecraft.server.MinecraftServer;
import net.minecraft.util.text.TextComponentString;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.common.SidedProxy;
import net.minecraftforge.fml.common.event.*;
import net.minecraftforge.fml.common.eventhandler.SubscribeEvent;
import net.minecraftforge.fml.common.gameevent.TickEvent;
import java.util.*;

@Mod(modid = "cubiclab", name = "CubicChunks Lab", version = "0.1.0", dependencies = "required-after:cubicchunks;after:riven")
public final class CubicLab {
    @SidedProxy(clientSide = "io.github.opencubicchunks.cubicchunks.lab.ClientProxy", serverSide = "io.github.opencubicchunks.cubicchunks.lab.CommonProxy")
    public static CommonProxy proxy;
    static LabJob active;
    private static final Map<String, LabJob> completed = new LinkedHashMap<>();
    private long tickStarted;
    @Mod.EventHandler public void preInit(FMLPreInitializationEvent event) {
        Network.initialize(); MinecraftForge.EVENT_BUS.register(this); proxy.initialize();
    }
    @Mod.EventHandler public void serverStarting(FMLServerStartingEvent event) { event.registerServerCommand(new LabCommand()); }
    @Mod.EventHandler public void stopping(FMLServerStoppingEvent event) {
        if (active != null) { active.failure = "Server stopped during test"; active.finish(); active = null; }
        LabJob.release(); LabHooks.serverPackets = null; completed.clear();
    }
    @SubscribeEvent public void tick(TickEvent.ServerTickEvent event) {
        if (event.phase == TickEvent.Phase.START) { tickStarted = System.nanoTime(); return; }
        LabJob job = active;
        if (job == null) return;
        try { job.tick(); } catch (Exception failure) { job.failure = failure.toString(); job.done = true; }
        if (job.started != 0) job.ticks.add(System.nanoTime() - tickStarted);
        if (job.done) {
            job.finish(); completed.put(job.id, job); active = null;
            while (completed.size() > 32) completed.remove(completed.keySet().iterator().next());
        }
    }
    @SubscribeEvent public void cubeLoad(CubeEvent.Load event) {
        if (!event.getWorld().isRemote && active != null && active.started != 0) active.cubeLoads++;
    }
    @SubscribeEvent public void cubeUnload(CubeEvent.Unload event) {
        if (!event.getWorld().isRemote && active != null && active.started != 0) active.cubeUnloads++;
    }
    @SubscribeEvent public void dataLoad(CubeDataEvent.Load event) {
        if (!event.getWorld().isRemote && active != null && active.started != 0) active.dataLoads++;
    }
    @SubscribeEvent public void dataSave(CubeDataEvent.Save event) {
        if (!event.getWorld().isRemote && active != null && active.started != 0) active.dataSaves++;
    }
    static void receive(EntityPlayerMP player, String message) {
        JsonObject json = new JsonParser().parse(message).getAsJsonObject();
        String id = json.get("runId").getAsString();
        LabJob job = active != null && active.id.equals(id) ? active : completed.get(id);
        if (job == null || !job.peers.contains(player.getUniqueID())) return;
        String op = json.get("op").getAsString();
        if (op.equals("ready") && job == active) job.ready.add(player.getUniqueID());
        if (op.equals("report")) {
            LabData.write(job.output.resolve("client-" + player.getUniqueID() + ".json"), json);
            job.server.sendMessage(new TextComponentString("CUBICLAB_CLIENT_RESULT runId=" + id + " player=" + player.getName()));
        }
    }
    static JsonObject control(String op, String id, String scenario) {
        JsonObject data = new JsonObject(); data.addProperty("op", op); data.addProperty("runId", id);
        data.addProperty("scenario", scenario); return data;
    }
    private static final class LabCommand extends CommandBase {
        public String getName() { return "cubiclab"; }
        public String getUsage(ICommandSender sender) { return "cubiclab run idle|generate|resident|save|load-sync|load-async|horizontal|vertical | status | release | cancel | quit"; }
        public int getRequiredPermissionLevel() { return 2; }
        public void execute(MinecraftServer server, ICommandSender sender, String[] args) throws CommandException {
            if (args.length == 2 && args[0].equals("run")) {
                if (active != null) throw new CommandException("A lab test is active");
                try { active = new LabJob(server, args[1]); }
                catch (Exception failure) { throw new CommandException(failure.getMessage()); }
                sender.sendMessage(new TextComponentString("CUBICLAB_STARTED runId=" + active.id + " scenario=" + args[1]));
                return;
            }
            if (args.length != 1) throw new CommandException(getUsage(sender));
            switch (args[0]) {
                case "status": sender.sendMessage(new TextComponentString(active == null ? "Cubic Lab idle" : active.scenario + " " + active.progress)); break;
                case "release": if (active != null) throw new CommandException("Cancel the active test first"); LabJob.release(); break;
                case "cancel": if (active != null) { active.failure = "Canceled by operator"; active.done = true; } break;
                case "quit":
                    if (active != null) throw new CommandException("Cancel the active test first");
                    LabJob.release();
                    for (EntityPlayerMP player : server.getPlayerList().getPlayers()) Network.CHANNEL.sendTo(new Network.ClientMessage(control("quit", "", "")), player);
                    break;
                default: throw new CommandException(getUsage(sender));
            }
        }
    }
}

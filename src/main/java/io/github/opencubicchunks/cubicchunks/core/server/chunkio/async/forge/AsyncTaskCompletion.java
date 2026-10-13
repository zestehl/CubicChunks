/*
 * Minecraft Forge
 * Copyright (c) 2016.
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation version 2.1
 * of the License.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
 */

package io.github.opencubicchunks.cubicchunks.core.server.chunkio.async.forge;

import java.util.Collection;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ThreadPoolExecutor;

/** Keeps completed I/O jobs discoverable while native events and callbacks finish on the server thread. */
final class AsyncTaskCompletion {
    private AsyncTaskCompletion() {
    }

    /** Finalize on the server thread, releasing resources even if loading or a callback fails. */
    static void complete(AsyncIOProvider<?> task) {
        task.beginCompletion();
        try {
            task.runSynchronousPart();
        } finally {
            task.cleanup();
        }
    }

    /** A shutdown timeout is not proof that an old reader has stopped using its column. */
    static void cleanupStoppedTasks(Iterable<? extends AsyncIOProvider<?>> tasks, Collection<? extends Runnable> neverStarted) {
        Set<Runnable> canceled = new HashSet<>(neverStarted);
        for (AsyncIOProvider<?> task : tasks) {
            if (task.isFinished() || canceled.contains(task)) {
                task.cleanup();
            }
        }
    }

    /** A running read still needs its column; only a task removed from the queue can release it now. */
    static <K, T extends AsyncIOProvider<?>> void cancelIfUnneeded(Map<K, T> tasks, K key, T task, ThreadPoolExecutor executor) {
        if (!task.hasCallbacks() && executor.remove(task)) {
            tasks.remove(key, task);
            task.cleanup();
        }
    }

    /** The caller must own the server thread; this does not move world mutation to I/O workers. */
    static <K, T extends AsyncIOProvider<?>> void drain(Map<K, T> tasks) {
        for (Map.Entry<K, T> entry : tasks.entrySet()) {
            T task = entry.getValue();
            if (task.isFinished() && task.claimCompletion()) {
                try {
                    // Same-coordinate requests from load events must still join this task.
                    if (task.hasCallbacks()) {
                        complete(task);
                    } else {
                        // An abandoned read must not publish entities, ticks or a column's
                        // cached cube without the provider consumer that registers the result.
                        task.cleanup();
                    }
                } finally {
                    // A callback may replace the entry; release only the instance we completed.
                    tasks.remove(entry.getKey(), task);
                }
            }
        }
    }
}

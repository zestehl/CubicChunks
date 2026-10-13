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

import java.util.Map;

/** Keeps completed I/O jobs discoverable while native events and callbacks finish on the server thread. */
final class AsyncTaskCompletion {
    private AsyncTaskCompletion() {
    }

    /** The caller must own the server thread; this does not move world mutation to I/O workers. */
    static <K, T extends AsyncIOProvider<?>> void drain(Map<K, T> tasks) {
        for (Map.Entry<K, T> entry : tasks.entrySet()) {
            T task = entry.getValue();
            if (task.isFinished() && task.claimCompletion()) {
                try {
                    // Same-coordinate requests from load events must still join this task.
                    task.runSynchronousPart();
                } finally {
                    // A callback may replace the entry; release only the instance we completed.
                    tasks.remove(entry.getKey(), task);
                }
            }
        }
    }
}

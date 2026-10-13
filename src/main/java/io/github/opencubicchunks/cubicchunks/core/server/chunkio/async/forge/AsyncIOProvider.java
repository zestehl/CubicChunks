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

import mcp.MethodsReturnNonnullByDefault;

import java.util.Objects;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.function.Consumer;

import javax.annotation.Nullable;
import javax.annotation.ParametersAreNonnullByDefault;

/**
 * Interface for grouping asynchronous world IO access together, synchronized to the start of the next tick
 * after loading finishes
 */
@MethodsReturnNonnullByDefault
@ParametersAreNonnullByDefault
abstract class AsyncIOProvider<T> implements Runnable {

    private final ConcurrentLinkedQueue<Consumer<T>> callbacks = new ConcurrentLinkedQueue<>();
    volatile boolean finished = false;
    private boolean completionClaimed;
    private boolean completionStarted;
    @Nullable private Runnable cleanup;

    /** Resource ownership is independent of consumers waiting for a result. Server thread only. */
    final void setCleanup(Runnable cleanup) {
        this.cleanup = cleanup;
    }

    /** Release once, including when native completion fails before it reaches the consumers. */
    final void cleanup() {
        Runnable cleanup = this.cleanup;
        this.cleanup = null;
        if (cleanup != null) {
            cleanup.run();
        }
    }

    /** Server-thread guard against completing this queued task again from a reentrant tick. */
    final boolean claimCompletion() {
        if (completionClaimed) {
            return false;
        }
        completionClaimed = true;
        return true;
    }

    /** Once native publication starts, provider consumers must finish registering the loaded result. */
    final void beginCompletion() {
        this.completionStarted = true;
    }

    /**
     * Add a callback to this access group, to be executed when the load finishes
     *
     * @param callback The callback to execute
     */
    void addCallback(Consumer<T> callback) {
        this.callbacks.add(callback);
    }

    /**
     * Remove a callback before native completion starts. Once publication begins, provider callbacks must finish.
     *
     * @param callback The callback to remove
     */
    void removeCallback(Consumer<T> callback) {
        removeCallback((Object) callback);
    }

    void removeCallback(Object callback) {
        if (completionStarted) {
            return;
        }
        Object identity = callbackIdentity(callback);
        for (Consumer<T> registered : callbacks) {
            if (identity.equals(callbackIdentity(registered)) && callbacks.remove(registered)) {
                return;
            }
        }
    }

    static <T> Consumer<T> withCallbackIdentity(Object identity, Consumer<T> callback) {
        return new CallbackWithIdentity<>(callbackIdentity(Objects.requireNonNull(identity)), Objects.requireNonNull(callback));
    }

    private static Object callbackIdentity(Object callback) {
        return callback instanceof CallbackWithIdentity ? ((CallbackWithIdentity<?>) callback).identity : callback;
    }

    /** Keep the original consumer or vanilla Runnable addressable through provider postprocessing. */
    private static final class CallbackWithIdentity<T> implements Consumer<T> {
        private final Object identity;
        private final Consumer<T> callback;

        CallbackWithIdentity(Object identity, Consumer<T> callback) {
            this.identity = identity;
            this.callback = callback;
        }

        @Override public void accept(T value) {
            callback.accept(value);
        }
    }

    /**
     * Run all callbacks waiting for the load. Assumes that the load is finished; calling this before is undefined
     * behavior.
     */
    void runCallbacks() {
        T value = this.get();
        RuntimeException failure = null;
        Consumer<T> callback;
        // Claim each callback before invoking it: callbacks can reenter completion or fail.
        while ((callback = this.callbacks.poll()) != null) {
            try {
                callback.accept(value);
            } catch (RuntimeException error) {
                // A failed consumer must not prevent the other waiting consumers from being notified.
                if (failure == null) {
                    failure = error;
                } else if (failure != error) {
                    failure.addSuppressed(error);
                }
            }
        }
        if (failure != null) {
            throw failure;
        }
    }

    /**
     * True if the target has been loaded and is available for use
     *
     * @return if this is finished
     */
    boolean isFinished() {
        return finished;
    }

    /**
     * Check if any callbacks are registered as waiting for this load.
     *
     * @return <code>true</code> if there is at least one callback waiting
     */
    boolean hasCallbacks() {
        return !callbacks.isEmpty();
    }

    /**
     * Finalize the loading operating synchronously from the main thread.
     */
    abstract void runSynchronousPart();

    /**
     * Retrive the loaded object. Undefined if the load hasn't finished yet
     *
     * @return The loaded object
     */
    @Nullable
    abstract T get();
}

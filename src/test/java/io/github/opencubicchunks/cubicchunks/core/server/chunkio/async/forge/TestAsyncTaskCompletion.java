/*
 *  This file is part of Cubic Chunks Mod, licensed under the MIT License (MIT).
 *
 *  Copyright (c) 2015-2021 OpenCubicChunks
 *  Copyright (c) 2015-2021 contributors
 *
 *  Permission is hereby granted, free of charge, to any person obtaining a copy
 *  of this software and associated documentation files (the "Software"), to deal
 *  in the Software without restriction, including without limitation the rights
 *  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 *  copies of the Software, and to permit persons to whom the Software is
 *  furnished to do so, subject to the following conditions:
 *
 *  The above copyright notice and this permission notice shall be included in
 *  all copies or substantial portions of the Software.
 *
 *  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 *  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 *  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 *  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 *  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 *  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 *  THE SOFTWARE.
 */
package io.github.opencubicchunks.cubicchunks.core.server.chunkio.async.forge;

import org.junit.Test;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Consumer;

import static org.junit.Assert.*;

/** Completion ownership tests require no Minecraft world or I/O threads. */
public class TestAsyncTaskCompletion {
    private static final class Task extends AsyncIOProvider<String> {
        int completions;

        Task(boolean finished) {
            this.finished = finished;
        }

        @Override public void run() {
            finished = true;
        }

        @Override void runSynchronousPart() {
            completions++;
            runCallbacks();
        }

        @Override String get() {
            return "loaded";
        }
    }

    @Test public void reentrantDrainCannotCompleteTheSameTaskTwice() {
        Map<String, Task> tasks = new ConcurrentHashMap<>();
        Task task = new Task(true);
        AtomicInteger callbacks = new AtomicInteger();
        task.addCallback(value -> {
            assertEquals("loaded", value);
            callbacks.incrementAndGet();
            AsyncTaskCompletion.drain(tasks);
        });
        tasks.put("column", task);
        AsyncTaskCompletion.drain(tasks);
        assertEquals(1, task.completions);
        assertEquals(1, callbacks.get());
        assertTrue(tasks.isEmpty());
    }

    @Test public void replacementQueuedByCallbackKeepsItsOwnership() {
        Map<String, Task> tasks = new ConcurrentHashMap<>();
        Task original = new Task(true);
        Task replacement = new Task(false);
        original.addCallback(value -> tasks.put("column", replacement));
        tasks.put("column", original);
        AsyncTaskCompletion.drain(tasks);
        assertSame(replacement, tasks.get("column"));
        assertEquals(1, original.completions);
        assertEquals(0, replacement.completions);
        replacement.run();
        AsyncTaskCompletion.drain(tasks);
        assertEquals(1, replacement.completions);
        assertTrue(tasks.isEmpty());
    }

    @Test public void unfinishedTaskRemainsQueued() {
        Map<String, Task> tasks = new ConcurrentHashMap<>();
        Task task = new Task(false);
        tasks.put("cube", task);
        AsyncTaskCompletion.drain(tasks);
        assertSame(task, tasks.get("cube"));
        assertEquals(0, task.completions);
    }

    @Test public void sameCoordinateRequestDuringCompletionJoinsExistingTask() {
        Map<String, Task> tasks = new ConcurrentHashMap<>();
        Task task = new Task(true);
        AtomicInteger joined = new AtomicInteger();
        task.addCallback(value -> {
            Task existing = tasks.get("cube");
            assertSame(task, existing);
            existing.addCallback(next -> joined.incrementAndGet());
            AsyncTaskCompletion.drain(tasks);
        });
        tasks.put("cube", task);
        AsyncTaskCompletion.drain(tasks);
        assertEquals(1, task.completions);
        assertEquals(1, joined.get());
        assertTrue(tasks.isEmpty());
    }

    @Test public void fatalErrorEscapesImmediatelyAndReleasesQueuedOwnership() {
        Map<String, Task> tasks = new ConcurrentHashMap<>();
        Task task = new Task(true);
        Error fatal = new AssertionError("fatal callback");
        AtomicInteger later = new AtomicInteger();
        task.addCallback(value -> { throw fatal; });
        task.addCallback(value -> later.incrementAndGet());
        tasks.put("cube", task);
        try {
            AsyncTaskCompletion.drain(tasks);
            fail("Fatal errors must not be treated as recoverable consumer failures");
        } catch (Error error) {
            assertSame(fatal, error);
        }
        assertEquals(0, later.get());
        assertTrue(tasks.isEmpty());
    }

    @Test public void failedCallbackStillNotifiesOtherConsumersAndReleasesTask() {
        Map<String, Task> tasks = new ConcurrentHashMap<>();
        Task task = new Task(true);
        RuntimeException failure = new IllegalStateException("consumer failure");
        AtomicInteger failures = new AtomicInteger(), cleanup = new AtomicInteger();
        task.addCallback(value -> { failures.incrementAndGet(); throw failure; });
        task.addCallback(value -> cleanup.incrementAndGet());
        tasks.put("cube", task);
        try {
            AsyncTaskCompletion.drain(tasks);
            fail("Callback failure must remain visible");
        } catch (RuntimeException error) {
            assertSame(failure, error);
        }
        assertTrue(tasks.isEmpty());
        assertEquals(1, cleanup.get());
        task.runCallbacks();
        AsyncTaskCompletion.drain(tasks);
        assertEquals(1, failures.get());
        assertEquals(1, task.completions);
    }

    @Test public void callbackFailuresPreserveSuppressedCauses() {
        Task task = new Task(true);
        RuntimeException first = new IllegalStateException("first");
        RuntimeException second = new IllegalArgumentException("second");
        task.addCallback(value -> { throw first; });
        task.addCallback(value -> { throw second; });
        task.addCallback(value -> { throw first; });
        try {
            task.runCallbacks();
            fail("Callback failure must remain visible");
        } catch (RuntimeException error) {
            assertSame(first, error);
            assertArrayEquals(new Throwable[] {second}, error.getSuppressed());
        }
        assertFalse(task.hasCallbacks());
    }

    @Test public void reentrantCallbackDrainClaimsEachConsumerOnce() {
        Task task = new Task(true);
        List<Integer> calls = new ArrayList<>();
        task.addCallback(value -> { calls.add(1); task.runCallbacks(); });
        task.addCallback(value -> calls.add(2));
        task.runCallbacks();
        assertEquals(Arrays.asList(1, 2), calls);
        assertFalse(task.hasCallbacks());
    }

    @Test public void callbackAddedDuringDispatchIsDeliveredAndRemovedCallbackIsSkipped() {
        Task task = new Task(true);
        List<Integer> calls = new ArrayList<>();
        Consumer<String> removed = value -> calls.add(99);
        task.addCallback(value -> { calls.add(1); task.addCallback(next -> calls.add(3)); });
        task.addCallback(removed);
        task.addCallback(value -> calls.add(2));
        task.removeCallback(removed);
        task.runCallbacks();
        assertEquals(Arrays.asList(1, 2, 3), calls);
        assertFalse(task.hasCallbacks());
    }

    @Test public void replacementSurvivesAnEarlierConsumerFailure() {
        Map<String, Task> tasks = new ConcurrentHashMap<>();
        Task original = new Task(true);
        Task replacement = new Task(false);
        RuntimeException failure = new IllegalStateException("consumer failure");
        original.addCallback(value -> { throw failure; });
        original.addCallback(value -> tasks.put("cube", replacement));
        tasks.put("cube", original);
        try {
            AsyncTaskCompletion.drain(tasks);
            fail("Callback failure must remain visible");
        } catch (RuntimeException error) {
            assertSame(failure, error);
        }
        assertSame(replacement, tasks.get("cube"));
    }
}

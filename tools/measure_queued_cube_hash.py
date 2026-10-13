#!/usr/bin/env python3
"""Compile the actual queue-key source and measure synthetic coordinate hashes.

Requires cached mapped Cleanroom 0.6.13-alpha and Forge 14.23.5.2860 JARs,
Guava 21.0, jsr305 3.0.2, JUnit 4.13.2, and hamcrest-core 1.3. It does not
download dependencies or launch Minecraft. A compile-only MCP nullability
annotation fixture supplies an annotation absent from the mapped JARs.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


PACKAGE = "io/github/opencubicchunks/cubicchunks/core/server/chunkio/async/forge"
ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--javac", type=Path, required=True, help="JDK 25 javac executable")
    parser.add_argument("--java25", type=Path, required=True)
    parser.add_argument("--java8", type=Path, required=True)
    parser.add_argument("--gradle-cache", type=Path, default=Path.home() / ".gradle/caches")
    parser.add_argument("--output", type=Path, default=ROOT / "cleanroom/build/hash-diagnostic")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    source = ROOT / "src/main/java" / PACKAGE / "QueuedCube.java"
    tests = [ROOT / "src/test/java" / PACKAGE / filename for filename in (
        "TestQueuedCubeHash.java", "QueuedCubeHashDiagnostic.java")]

    def dependency(group, artifact, version):
        directory = args.gradle_cache / "modules-2/files-2.1" / group / artifact / version
        matches = sorted(directory.glob("*/" + artifact + "-" + version + ".jar"))
        if not matches:
            raise FileNotFoundError("Required dependency is not cached: " + str(directory))
        return matches[0]

    libraries = [dependency(*coordinates) for coordinates in (
        ("com.google.guava", "guava", "21.0"),
        ("com.google.code.findbugs", "jsr305", "3.0.2"),
        ("junit", "junit", "4.13.2"),
        ("org.hamcrest", "hamcrest-core", "1.3"))]
    fixture = output / "fixture/mcp/MethodsReturnNonnullByDefault.java"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text("package mcp; public @interface MethodsReturnNonnullByDefault {}\n", encoding="utf-8")
    separator = os.pathsep
    records = []

    def run(directory, label, command, expected=0):
        command = list(map(str, command))
        result = subprocess.run(command, capture_output=True, text=True)
        (directory / (label + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
        record = {"label": label, "args": command, "exit_code": result.returncode}
        if (expected == 0 and result.returncode != 0) or (expected != 0 and result.returncode == 0):
            raise RuntimeError(label + ": unexpected exit code " + str(result.returncode)
                               + "\n" + result.stdout + result.stderr)
        return result, record

    for profile, java, name in (
        ("cleanroom-0.6.13-alpha", args.java25, "java25"),
        ("forge-1.12.2-14.23.5.2860", args.java8, "java8")):
        mapped = (args.gradle_cache / "unimined/maven/net/minecraft" / ("minecraft-" + profile)
                  / "1.12.2" / ("minecraft-" + profile + "-1.12.2.jar"))
        if not mapped.is_file():
            raise FileNotFoundError("Required mapped API is not cached: " + str(mapped))
        directory = output / name
        classes = directory / "classes"
        classes.mkdir(parents=True, exist_ok=True)
        classpath = separator.join(map(str, [mapped] + libraries))
        commands = []
        compile_command = [args.javac, "--release", "8", "-proc:none", "-cp", classpath,
                           "-d", classes, fixture, source] + tests
        _, record = run(directory, "compile", compile_command)
        commands.append(record)
        runtime_classpath = str(classes) + separator + classpath
        test_command = [java, "-cp", runtime_classpath, "org.junit.runner.JUnitCore",
                        PACKAGE.replace("/", ".") + ".TestQueuedCubeHash"]
        _, record = run(directory, "tests", test_command)
        commands.append(record)
        result, record = run(directory, "diagnostic", [java, "-cp", runtime_classpath,
                            PACKAGE.replace("/", ".") + ".QueuedCubeHashDiagnostic"])
        commands.append(record)
        csv = output / ("hash-distribution-" + name + ".csv")
        csv.write_text(result.stdout, encoding="utf-8")
        result, record = run(directory, "java-version", [java, "-version"])
        commands.append(record)
        records.append({"profile": profile, "java_version": result.stdout + result.stderr,
                        "commands": commands, "csv": str(csv),
                        "mapped_api_sha256": hashlib.sha256(mapped.read_bytes()).hexdigest()})
        print(profile + ": source compiled for Java 8, tests passed, CSV written to " + str(csv))

    # Verify the regressions detect the original hash; only a temporary source copy changes.
    control = output / "negative-control"
    baseline = control / "source/QueuedCube.java"
    baseline.parent.mkdir(parents=True, exist_ok=True)
    replacement, count = re.subn(
        r"static int hashCoordinates\(int x, int y, int z\) \{.*?\n    \}",
        "static int hashCoordinates(int x, int y, int z) {\n"
        "        return x * 31 + y * 23 * z * 29;\n    }",
        source.read_text(encoding="utf-8"), count=1, flags=re.S)
    if count != 1:
        raise RuntimeError("Could not construct original-expression negative control")
    baseline.write_text(replacement, encoding="utf-8")
    classes = control / "classes"
    classes.mkdir(parents=True, exist_ok=True)
    compile_command = records[0]["commands"][0]["args"][:]
    compile_command[compile_command.index("-d") + 1] = str(classes)
    compile_command[compile_command.index(str(source))] = str(baseline)
    _, compile_record = run(control, "compile", compile_command)
    test_command = records[0]["commands"][1]["args"][:]
    cp_index = test_command.index("-cp") + 1
    test_command[cp_index] = str(classes) + separator + test_command[cp_index].split(separator, 1)[1]
    _, test_record = run(control, "tests", test_command, expected=1)

    summary = {
        "scope": "Synthetic hash distributions only; no Minecraft world, native runtime, or timing measurement."
                 " Compile-time MCP nullability annotation fixture only.",
        "source_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in [source] + tests + [Path(__file__).resolve()]},
        "runs": records,
        "negative_control": {"method": "Original coordinate expression in a temporary source copy",
                             "commands": [compile_record, test_record]},
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("Original-expression negative control failed as expected; summary.json records commands and source hashes.")


if __name__ == "__main__":
    main()

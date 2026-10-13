# Queue-key hash distribution

The original cube queue hash multiplies Y by Z, so a vertical line at Z = 0
has one hash regardless of its height. Independent coordinate mixing gives
all 16,384 keys distinct hashes in the measured vertical sample. The same
result holds for the horizontal sample and origin plane. In the 32-by-32-by-32
volume, distinct hashes increase from 6,208 to 32,768.

These are measured synthetic hash distributions, not native Minecraft
performance measurements. Both formulas use the same coordinate sets and a
world-hash contribution of zero. Equal-hash group counts are independent of
that common XOR contribution. The raw CSV also includes a fixed 32,768-slot
bucket model; bucket collisions still occur with the revised formula.

[PNG chart](hash-distribution.png), [SVG chart](hash-distribution.svg),
[Java 25 CSV](hash-distribution-java25.csv), [Java 8 CSV](hash-distribution-java8.csv),
and [results with source hashes](result.json) are retained together. The
Java 25 and Java 8 captures agree exactly.

From the repository root, reproduce the measurements using cached dependencies
and explicit JDK executable paths:

```text
python tools/measure_queued_cube_hash.py --javac <jdk25-javac> --java25 <jdk25-java> --java8 <jdk8-java>
python cleanroom/tools/plot_hash_distribution.py
```

The plotting script requires Matplotlib and NumPy. Both scripts accept
`--output`; the plot script accepts `--input` for a different measurement
directory. Raw compilation, test and negative-control logs plus exact commands
remain in `cleanroom/build/hash-diagnostic/`.

The measurement script compiles the actual queue-key source with `--release 8`
against mapped Cleanroom 0.6.13-alpha and Forge 14.23.5.2860 APIs. It supplies
only a compile-time MCP nullability annotation fixture. The focused tests run
on Java 25 and Java 8. A temporary source copy using the original coordinate
expression fails the regressions; the worktree and dependency JARs are not
changed by that control. No Minecraft world is constructed.

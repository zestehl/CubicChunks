# Native performance graphs

lighting-pass-02  |  2026-10-13  |  Cleanroom 0.7.0-alpha / Java 25  |  native client + dedicated server

Reproduce these figures with `tools/plot_cubic_lab_results.py --report <retained-results.json> --output <new-directory>`. This command builds nothing and launches no game.

PNG files provide previews; SVG files preserve editable vector text. `graph-data.csv` retains exact timing fields, sample counts and run IDs. The snapshot correctness probe remains in the CSV but is excluded from the timing plots. Source/plotter hashes and exact mod inputs are in `provenance.json`.

Tick windows include world/lab work. Async latency includes queueing and tick dispatch; sync timers measure a different boundary. Save-call totals and flush time are not whole-workload duration or disk throughput. One host/run with active JFR is descriptive evidence, not a controlled speedup study.

![Server tick durations](server-timing-tails.png)

![Client frame intervals](client-timing-tails.png)

![Stored-cube reload latency](cube-reload-latency.png)

![Cube save submission and flush](cube-save-costs.png)

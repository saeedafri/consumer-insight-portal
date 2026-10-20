# Validation scripts

These scripts were actually executed during the review. Raw outputs are in `../evidence/`.

## source_probes.py

Requires Python 3 and the original extracted source tree. Extracts selected functions using AST and executes them with fake database objects. Do not use it to execute arbitrary untrusted repositories. It does not run the full application, prove security or replace integration tests.

```bash
python source_probes.py /path/to/extracted/repository --out source-probes.json
```

## data_path_probe.py

Requires Python 3, pandas and a Unix-like environment with the `resource` module. Use Linux for direct comparison with the recorded RSS figures. The original run used Python 3.13.5 and pandas 2.2.3; it is not a qualification of the application's declared dependency versions.

```bash
python data_path_probe.py --rows 1000000 --repeats 5 --out data-path-results.json
```

The full-dataframe path exceeded 1 GiB process peak RSS in the recorded run. Do not run it in production or on a memory-constrained shared host. Lower `--rows` for a small functional trial. The temporary database contains only synthetic data and is removed when the script finishes normally.

The script's RSS field names reflect the Linux run; macOS reports `ru_maxrss` in different units. Five samples are not a reliable p95/p99 estimate. This is a data-path experiment, not a browser, framework, network, concurrency or Azure benchmark.

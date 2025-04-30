# FHIR De-Identification Utility

`deidentify_fhir.py` is a dependency-free command-line tool that removes or anonymizes
Protected Health Information (PHI) from FHIR JSON resources.  It was written with
HIPAA Safe-Harbor requirements in mind and can be integrated into ETL pipelines or
run ad-hoc from the shell.

---

## Features

* **Removes HIPAA direct identifiers** according to a configurable policy.
* **Deterministically hashes** identifiers you still need (e.g. MRN) using SHA-256 + salt.
* **Shifts dates by ±N days** (deterministic per patient) while preserving relative timelines.
* **Safe-Harbor mode** collapses dates to year precision & aggregates ages ≥ 90.
* **Streaming support** – read/write from `stdin` / `stdout` with `-`.
* **Zero external dependencies** — pure Python ≥ 3.9.

---

## Quick start

```bash
# install
pip install .  # editable install: `pip install -e .`

# run on a single resource
deidentify-fhir input.json --salt-file /run/secrets/deid_salt --verbose

# Unix pipeline (stdin/stdout)
cat bundle.json | deidentify-fhir - --safe-harbor --output - > bundle_deid.json
```

The CLI help screen lists all available options:

```bash
deidentify-fhir --help
```

---

## Project structure

```
.
├── deidentify_fhir.py   # tool implementation & CLI
├── README.md            # this file
├── pyproject.toml       # build / packaging metadata
├── tests/               # minimal pytest suite
└── .gitignore
```

---

## Development

1. Create a virtualenv: `python -m venv .venv && source .venv/bin/activate`.
2. Install in editable mode with test extras: `pip install -e '.[dev]'`.
3. Run tests: `pytest`.

Feel free to open PRs with bug-fixes or policy improvements.

---

## License

MIT © 2025 Joe Bartlett
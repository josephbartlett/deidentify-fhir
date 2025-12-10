# FHIR De-Identification Utility

`deidentify_fhir.py` is a dependency-free command-line tool that removes or anonymizes
Protected Health Information (PHI) from FHIR JSON resources.  It was written with
HIPAA Safe-Harbor requirements in mind and can be integrated into ETL pipelines or
run ad-hoc from the shell.

This is example tooling and not a legal guarantee of HIPAA compliance; organizations must perform their own validation and governance.

---

## Features

* **Removes HIPAA direct identifiers** according to a configurable policy.
* **Deterministically hashes** identifiers you still need (e.g. MRN) using SHA-256 + salt.
* **Shifts dates by ±N days** (deterministic per patient) while preserving relative timelines *(disabled with `--safe-harbor`)*.
* **Safe-Harbor mode** truncates all dates to year precision, aggregates ages ≥ 90, and turns off date shifting.
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


## Policy customization

The built-in `PHI_POLICY` in `deidentify_fhir.py` defines which fields are removed for each resource type. Provide a JSON file with `--policy` to override or extend these defaults.

Example `policy.json`:

```json
{
  "Patient": ["name", "address"],
  "Observation": ["identifier"]
}
```

Run with:

```bash
deidentify-fhir input.json --policy policy.json --salt-file /run/secrets/deid_salt
```

### Hashing additional identifier systems

Identifiers whose `system` URI appears in `HASHED_IDENTIFIER_SYSTEMS` are kept after hashing. When extending `PHI_POLICY`, also add any identifier systems you wish to retain in hashed form:

```python
# deidentify_fhir.py
PHI_POLICY = { ... }
HASHED_IDENTIFIER_SYSTEMS = {
    "http://hospital.example.org/mrn",
    "http://registry.example/nhs-number",  # custom system
}
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

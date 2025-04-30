# Ensure project root on import path so `deidentify_fhir` module is discoverable
import pathlib, sys, os

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deidentify_fhir import pseudonymise_identifier  # noqa: E402


def test_hash_deterministic():
    salt = "s3cr3t"
    ident = {"system": "http://hospital.example.org/mrn", "value": "12345"}
    first = pseudonymise_identifier(ident, salt)
    second = pseudonymise_identifier(ident, salt)
    assert first == second
    assert first["value"] != "12345"  # actually hashed
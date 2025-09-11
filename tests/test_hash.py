from deidentify_fhir import pseudonymise_identifier


def test_hash_deterministic_default_length():
    salt = "s3cr3t"
    ident = {"system": "http://hospital.example.org/mrn", "value": "12345"}
    first = pseudonymise_identifier(ident, salt)
    second = pseudonymise_identifier(ident, salt)
    assert first == second
    assert first["value"] != "12345"  # actually hashed
    assert len(first["value"]) == 64  # full digest by default


def test_hash_truncation():
    salt = "s3cr3t"
    ident = {"system": "http://hospital.example.org/mrn", "value": "12345"}
    masked = pseudonymise_identifier(ident, salt, hash_length=16)
    assert len(masked["value"]) == 16

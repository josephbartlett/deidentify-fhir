from deidentify_fhir import pseudonymise_identifier


def test_hash_deterministic():
    salt = "s3cr3t"
    ident = {"system": "http://hospital.example.org/mrn", "value": "12345"}
    first = pseudonymise_identifier(ident, salt)
    second = pseudonymise_identifier(ident, salt)
    assert first == second
    assert first["value"] != "12345"  # actually hashed

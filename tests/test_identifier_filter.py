from deidentify_fhir import deidentify_resource


def test_identifier_whitelist():
    resource = {
        "resourceType": "Patient",
        "id": "abc",
        "identifier": [
            {"system": "http://hospital.example.org/mrn", "value": "12345"},
            {"system": "http://example.org/other", "value": "should_drop"},
        ],
    }

    deid = deidentify_resource(resource, salt="s", shift_days=0)

    # Only the whitelisted system should survive
    identifiers = deid.get("identifier", [])
    assert len(identifiers) == 1
    assert identifiers[0]["system"] == "http://hospital.example.org/mrn"
    assert identifiers[0]["value"] != "12345"

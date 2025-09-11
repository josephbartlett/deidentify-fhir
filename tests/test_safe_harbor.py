from deidentify_fhir import deidentify_resource


def test_safe_harbor_truncates_and_preserves_years():
    patient = {
        "resourceType": "Patient",
        "id": "p1",
        "birthDate": "1985-04-12",
    }
    encounter = {
        "resourceType": "Encounter",
        "id": "e1",
        "subject": {"reference": "Patient/p1"},
        "period": {
            "start": "2024-01-01T00:00:00Z",
            "end": "2024-01-02T00:00:00Z",
        },
    }

    deid_patient = deidentify_resource(patient, salt="s", shift_days=None, safe_harbor=True)
    assert deid_patient["birthDate"] == "1985"

    deid_encounter = deidentify_resource(encounter, salt="s", shift_days=None, safe_harbor=True)
    assert deid_encounter["period"]["start"] == "2024"
    assert deid_encounter["period"]["end"] == "2024"


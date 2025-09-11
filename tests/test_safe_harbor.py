from deidentify_fhir import deidentify_resource


def test_safe_harbor_truncates_skips_shifting_and_bins_ages():
    """Safe Harbor should collapse dates to years, ignore offsets and bin old ages."""

    patient = {
        "resourceType": "Patient",
        "id": "p1",
        # Older than 90 so should be binned to 1900
        "birthDate": "1920-04-12",
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

    # Pass a large shift that would change the year if applied
    deid_patient = deidentify_resource(patient, salt="s", shift_days=365, safe_harbor=True)
    assert deid_patient["birthDate"] == "1900"

    deid_encounter = deidentify_resource(encounter, salt="s", shift_days=365, safe_harbor=True)
    # Dates should be truncated to the year and unaffected by shifting
    assert deid_encounter["period"]["start"] == "2024"
    assert deid_encounter["period"]["end"] == "2024"


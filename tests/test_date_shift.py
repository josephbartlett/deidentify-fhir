import datetime as _dt

from deidentify_fhir import deidentify_resource, _parse_fhir_date


def test_period_start_shifted():
    resource = {
        "resourceType": "Encounter",
        "id": "enc",
        "period": {
            "start": "2024-01-01T00:00:00Z",
            "end": "2024-01-02T00:00:00Z",
        },
    }

    shift = 10
    deid = deidentify_resource(resource, salt="x", shift_days=shift)

    start_shifted = deid["period"]["start"]
    dt_orig, _ = _parse_fhir_date("2024-01-01T00:00:00Z")
    dt_shifted, _ = _parse_fhir_date(start_shifted)

    assert (dt_shifted - dt_orig).days == shift

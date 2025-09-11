import datetime as _dt
import pytest

from deidentify_fhir import deidentify_resource, _parse_fhir_date, shift_date


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
    dt_orig, _, _ = _parse_fhir_date("2024-01-01T00:00:00Z")
    dt_shifted, _, _ = _parse_fhir_date(start_shifted)

    assert (dt_shifted - dt_orig).days == shift


@pytest.mark.parametrize(
    "timestamp, offset, tz, frac",
    [
        ("2024-01-01T00:00:00.1Z", 5, "Z", 1),
        ("2024-01-01T00:00:00.123+02:00", -7, "+02:00", 3),
        ("2024-01-01T00:00:00.123456-07:00", 3, "-07:00", 6),
    ],
)
def test_fractional_seconds_and_timezone_preserved(timestamp, offset, tz, frac):
    dt_orig, tz_orig, frac_orig = _parse_fhir_date(timestamp)
    assert tz_orig == tz
    assert frac_orig == frac

    shifted = shift_date(timestamp, offset)
    dt_shifted, tz_shifted, frac_shifted = _parse_fhir_date(shifted)

    assert tz_shifted == tz
    assert frac_shifted == frac
    assert (dt_shifted - dt_orig).days == offset

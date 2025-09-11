#!/usr/bin/env python3
"""
deidentify_fhir.py
------------------
De-identifies a FHIR JSON resource.

Usage
=====
    python deidentify_fhir.py <input.json> [-o OUTPUT] [--salt SALT] [--shift-days N]
                               [--policy POLICY.json] [--verbose]

The script:
  • removes direct identifiers (name, address, telecom, MRN, photos, etc.)
  • replaces identifiers you still need with deterministic SHA-256 hashes
  • shifts every date | dateTime | instant by N days (default ±90, deterministic)
  • preserves everything else (codes, values, references, extensions)

Dependencies
============
Only the Python stdlib – no external packages required.
Tested on Python 3.9 – 3.12.

Author
======
Joe Bartlett — Apr 2025
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import random
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

##########################
# 1.  CONFIGURATION      #
##########################

# Fields to *remove* for each resourceType.
# Hash-pseudonymisation is used for elements in HASHED_FIELDS (identifiers you may still
# need for linkage). Adjust to your internal policy as required.
# Built-in Safe-Harbor oriented policy. Can be extended/overridden via --policy.
# This list aims to remove all 18 HIPAA identifiers when feasible within generic FHIR.
# NOTE: A single static list can never be fully complete; review for your dataset.
PHI_POLICY: Dict[str, List[str]] = {
    # Core demographics
    "Patient": [
        "identifier",              # hashed if in HASHED_IDENTIFIER_SYSTEMS
        "name",
        "telecom",
        "address",
        "photo",
        "birthDate",
        "contact",
        "communication",
        "multipleBirthBoolean",
        "multipleBirthInteger",
        "generalPractitioner",
        "managingOrganization",
        "link",
    ],
    # Providers / organisations
    "Practitioner": ["identifier", "name", "telecom", "address", "photo"],
    "PractitionerRole": ["telecom", "phone", "address"],
    "Organization": ["identifier", "telecom", "address"],
    "Endpoint": ["address"],
    # Device identifiers
    "Device": ["identifier", "udiCarrier"],
    # Encounters & visits
    "Encounter": ["identifier", "location"],
    "Location": ["identifier", "address", "telecom"],
    # Claims / billing
    "Claim": ["identifier"],
    # Clinical data that may carry identifiers
    "Observation": ["identifier"],
    "Condition": ["identifier"],
    "MedicationRequest": ["identifier"],
    "ImagingStudy": ["identifier"],
    # Fallback
    "*": ["identifier"],
}

# Which identifier systems should be hashed rather than removed.
# Extend as needed (MRN, SSN, etc.)
# Identifier.system values that are retained (after hashing). Any identifier
# with a system not listed here is removed entirely.
HASHED_IDENTIFIER_SYSTEMS = {
    "http://hospital.example.org/mrn",
    "urn:system:mrn",
}

# Placeholder used when user does not provide their own secret. Using this value
# unchanged is strongly discouraged and will trigger a runtime warning.
DEFAULT_SALT_PLACEHOLDER = "change-me-salt"

FHIR_DATE_RE = re.compile(
    r"^\d{4}-\d{2}(-\d{2}(T\d{2}:\d{2}(:\d{2}(?:\.\d{1,6})?)?(Z|[+-]\d{2}:\d{2})?)?)?$"
)
DATE_KEY_SUFFIXES = ("date", "datetime", "instant")

##########################
# 2.  CORE LOGIC         #
##########################


def load_resource(path: str | os.PathLike) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_resource(resource: Dict[str, Any], output_path: str | os.PathLike) -> None:
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(resource, f, indent=2, ensure_ascii=False)
        f.write("\n")


def sha256_hash(value: str, salt: str) -> str:
    return hashlib.sha256((salt + value).encode()).hexdigest()[:16]  # first 16 hex chars


def pseudonymise_identifier(identifier: Dict[str, Any], salt: str) -> Dict[str, Any]:
    """
    Mask an identifier by hashing its value with the given salt.
    Keeps the `system` field if present, drops all other sub-fields except the masked `value`.
    Returns an empty dict if no value is present.
    """
    # Extract original value; nothing to mask if value absent
    original = identifier.get("value")
    if original is None:
        return {}

    # Compute deterministic hash of the original value
    masked_value = sha256_hash(str(original), salt)
    # Build masked identifier with only system (if any) and hashed value
    masked: Dict[str, Any] = {"value": masked_value}
    if "system" in identifier:
        masked["system"] = identifier["system"]
    return masked


def _parse_fhir_date(value: str) -> tuple[_dt.datetime | None, str, int]:
    """Best-effort parse of a FHIR date/dateTime/instant string.

    Returns ``(datetime_obj_or_None, tz_suffix, fractional_precision)`` where
    ``tz_suffix`` preserves the original timezone designator ("Z" or e.g.
    "+02:00") and ``fractional_precision`` is the number of digits in the
    fractional seconds component (0 if absent) so we can round‑trip exactly.
    """
    try:
        # Separate timezone suffix so we can re-attach later.
        if value.endswith("Z"):
            core, suffix = value[:-1], "Z"
        elif "+" in value[10:] or "-" in value[10:]:  # timezone offset present
            # Find the last + or - after the date part
            for i in range(len(value) - 6, 9, -1):
                if value[i] in "+-":
                    core, suffix = value[:i], value[i:]
                    break
            else:
                core, suffix = value, ""
        else:
            core, suffix = value, ""

        # Detect fractional seconds precision before parsing
        frac_precision = 0
        if "." in core:
            frac_precision = len(core.split(".")[1])

        if len(core) == 4:
            dt = _dt.datetime(int(core), 1, 1)
        elif len(core) == 7:
            dt = _dt.datetime.strptime(core, "%Y-%m")
        elif len(core) == 10:
            dt = _dt.datetime.strptime(core, "%Y-%m-%d")
        else:
            dt = _dt.datetime.fromisoformat(core)
        return dt, suffix, frac_precision
    except Exception:
        return None, "", 0


def _format_fhir_date(
    original: str, shifted: _dt.datetime, suffix: str, frac_precision: int
) -> str:
    """Format ``shifted`` to match the precision of ``original`` and attach suffix."""
    length = len(original.rstrip("Z"))  # exclude Z when measuring precision
    if length == 4:
        return f"{shifted.year:04d}"
    elif length == 7:
        return shifted.strftime("%Y-%m")
    elif length == 10:
        return shifted.strftime("%Y-%m-%d")
    else:
        if frac_precision > 0:
            iso = shifted.isoformat(timespec="microseconds")
            if frac_precision < 6:
                iso = iso[: -(6 - frac_precision)]
            return iso + suffix
        else:
            return shifted.isoformat(timespec="seconds") + suffix


def shift_date(value: str, offset_days: int, collapse_to_year: bool = False) -> str:
    """Shift a FHIR date/dateTime/instant by ``offset_days``.

    If ``collapse_to_year`` is True, no shifting occurs and only the year component is
    returned (HIPAA Safe Harbor compliant). Time-zones are preserved otherwise.
    """
    dt, tz_suffix, frac_precision = _parse_fhir_date(value)
    if dt is None:
        return value  # give up – leave unchanged, but caller may warn/log

    if collapse_to_year:
        # Skip shifting entirely when collapsing to year precision
        return f"{dt.year:04d}"

    shifted = dt + _dt.timedelta(days=offset_days)

    return _format_fhir_date(value, shifted, tz_suffix, frac_precision)


def recursively_deidentify(
    obj: Any,
    salt: str,
    offset_days: int,
    *,
    collapse_dates: bool = False,
    safe_harbor: bool = False,
) -> Any:
    if isinstance(obj, dict):
        resource_type = obj.get("resourceType")
        # Determine which PHI fields apply
        phi_fields = list(PHI_POLICY.get(resource_type, []))
        if resource_type != "*":
            # Append generic rules, avoid duplicates
            phi_fields += [f for f in PHI_POLICY.get("*", []) if f not in phi_fields]
        if safe_harbor and "birthDate" in phi_fields:
            phi_fields.remove("birthDate")

        new_obj: Dict[str, Any] = {}
        for key, val in obj.items():
            # Remove PHI fields
            if key in phi_fields:
                if key == "identifier":
                    identifiers = val if isinstance(val, list) else [val]
                    kept: List[Dict[str, Any]] = []

                    for ident in identifiers:
                        system = ident.get("system")

                        # Keep only whitelisted systems (if system absent we drop)
                        if system and system in HASHED_IDENTIFIER_SYSTEMS:
                            processed = pseudonymise_identifier(ident, salt)
                            if processed:
                                kept.append(processed)

                    if kept:
                        new_obj[key] = kept if isinstance(val, list) else kept[0]
                # Skip all other PHI keys outright
                continue

            # Date shifting – only parse strings that look like dates
            if isinstance(val, str):
                key_lower = key.lower()
                if key_lower.endswith(DATE_KEY_SUFFIXES) or FHIR_DATE_RE.fullmatch(val):
                    dt_obj, _, _ = _parse_fhir_date(val)
                    if dt_obj is not None:
                        shifted_val = shift_date(val, offset_days, collapse_to_year=collapse_dates)
                        if safe_harbor and key == "birthDate":
                            try:
                                year = int(shifted_val[:4])
                                age = _dt.date.today().year - year
                                if age >= 90:
                                    shifted_val = "1900"
                            except Exception:
                                pass
                        new_obj[key] = shifted_val
                        continue
            # Recurse
            new_obj[key] = recursively_deidentify(
                val,
                salt,
                offset_days,
                collapse_dates=collapse_dates,
                safe_harbor=safe_harbor,
            )
        return new_obj
    elif isinstance(obj, list):
        return [
            recursively_deidentify(
                i, salt, offset_days, collapse_dates=collapse_dates, safe_harbor=safe_harbor
            )
            for i in obj
        ]
    else:
        return obj  # primitives unchanged


def deterministic_offset(base_salt: str, patient_id: str) -> int:
    """Returns a deterministic ±offset days (-90..+90) per patient_id."""
    h = hashlib.sha256((base_salt + patient_id).encode()).digest()
    rand_int = int.from_bytes(h[:4], "big")
    return (rand_int % 181) - 90  # 0-180 → -90..+90


def deidentify_resource(
    resource: Dict[str, Any],
    salt: str,
    shift_days: int | None,
    *,
    safe_harbor: bool = False,
) -> Dict[str, Any]:
    """Driver function for a single FHIR resource."""
    # If patient‐level identifier exists, derive deterministic offset
    if resource.get("resourceType") == "Patient":
        patient_id = resource.get("id", "")
    else:
        # FHIR often represents the subject reference as either a Dict or a
        # plain string (e.g. "Patient/123"). Handle both.
        subject = resource.get("subject") or resource.get("patient") or ""
        if isinstance(subject, dict):
            patient_id = subject.get("reference", "")
        elif isinstance(subject, str):
            patient_id = subject
        else:
            patient_id = ""
    if safe_harbor:
        offset = 0
        collapse = True
    else:
        offset = shift_days if shift_days is not None else deterministic_offset(salt, patient_id)
        collapse = False
    return recursively_deidentify(
        resource,
        salt,
        offset,
        collapse_dates=collapse,
        safe_harbor=safe_harbor,
    )


##########################
# 3.  CLI HANDLER        #
##########################

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="De-identify a FHIR JSON resource.")
    ap.add_argument("input", help="Path to input FHIR JSON file")
    ap.add_argument("-o", "--output", help="Output path (default: <input>_deid.json)")
    ap.add_argument(
        "--salt",
        default=DEFAULT_SALT_PLACEHOLDER,
        help="Secret salt for hashing (discouraged – prefer --salt-file or DEID_SALT)",
    )
    ap.add_argument(
        "--salt-file",
        help="Path to a file containing the secret salt (takes precedence over --salt)",
    )
    ap.add_argument(
        "--shift-days",
        type=int,
        help="Shift all dates by N days (if omitted, a deterministic random offset is used)",
    )
    ap.add_argument(
        "--policy",
        help="Optional JSON file overriding the built-in PHI policy (see README)",
    )
    ap.add_argument("--verbose", action="store_true", help="Verbose logging to stderr")

    ap.add_argument(
        "--safe-harbor",
        action="store_true",
        help="Enable HIPAA Safe Harbor mode: collapse dates to year precision and aggregate ages ≥90.",
    )
    return ap.parse_args()


def main() -> None:
    args = parse_args()

    # 1. Load external policy if provided (merge rather than replace)
    if args.policy:
        try:
            with open(args.policy, "r", encoding="utf-8") as fh:
                user_policy = json.load(fh)
            # Merge – user entries override built-ins
            for k, v in user_policy.items():
                PHI_POLICY[k] = v
        except Exception as e:
            sys.exit(f"[ERROR] Cannot load policy file {args.policy}: {e}")

    # 2. Obtain salt securely
    salt: str | None = None
    if args.salt_file:
        try:
            salt = Path(args.salt_file).read_text(encoding="utf-8").strip()
        except Exception as e:
            sys.exit(f"[ERROR] Cannot read salt file {args.salt_file}: {e}")
    else:
        salt = os.getenv("DEID_SALT", args.salt)

    if not salt or salt == DEFAULT_SALT_PLACEHOLDER:
        print(
            "[WARN] Using the default salt. Provide a strong secret via --salt, --salt-file or DEID_SALT.",
            file=sys.stderr,
        )

    # Allow streaming using "-" as stdin/stdout
    streaming_mode = args.input == "-"
    output_to_stdout = args.output == "-"

    if streaming_mode:
        input_path = None
        output_path = None if not args.output else Path(args.output)
    else:
        input_path = Path(args.input)
        if output_to_stdout:
            output_path = None
        else:
            output_path = (
                Path(args.output)
                if args.output
                else Path(args.input).with_stem(Path(args.input).stem + "_deid")
            )


    try:
        if streaming_mode:
            resource = json.load(sys.stdin)
        else:
            resource = load_resource(input_path)
    except Exception as e:
        src = "stdin" if streaming_mode else str(input_path)
        sys.exit(f"[ERROR] Cannot read {src}: {e}")

    deid = deidentify_resource(
        resource, salt, args.shift_days, safe_harbor=args.safe_harbor
    )


    try:
        if (streaming_mode and output_path is None) or output_to_stdout:
            json.dump(deid, sys.stdout, indent=2, ensure_ascii=False)
            sys.stdout.write("\n")
        else:
            # mypy: ignore[arg-type]
            save_resource(deid, output_path)
    except Exception as e:
        dst = "stdout" if ((streaming_mode and output_path is None) or output_to_stdout) else str(output_path)
        sys.exit(f"[ERROR] Cannot write {dst}: {e}")

    if args.verbose:
        removed = set(PHI_POLICY.get(resource.get("resourceType"), []) + PHI_POLICY.get("*", []))

        src_name = "stdin" if streaming_mode else input_path.name
        dst_name = "stdout" if ((streaming_mode and output_path is None) or output_to_stdout) else str(output_path)
        print(f"[INFO] De-identified {src_name} → {dst_name}", file=sys.stderr)
        print(f"[INFO] Policy removed fields: {sorted(removed)}", file=sys.stderr)


if __name__ == "__main__":
    main()

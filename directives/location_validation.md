# Directive: Location Validation

Layer 1 (Directive). Rules for accepting and validating UAE delivery locations.

## Goal

Every order must have a location precise enough for the courier to deliver without
calling the customer twice.

## Required location fields

| Field | Requirement |
|---|---|
| emirate | Must be one of the 7 known UAE emirates |
| area | District or neighbourhood name |
| address | Building/villa number + street + landmark (min ~10 characters) |
| maps_link | Google Maps URL or WhatsApp live location (strongly preferred) |

## Known emirates

Dubai, Sharjah, Ajman, Umm Al Quwain, Ras Al Khaimah, Fujairah, Abu Dhabi

## Rules

1. Any missing mandatory field → **High Risk / Do Not Pack**.
2. Unrecognised emirate → **High Risk / Do Not Pack**.
3. Address too short (< 10 chars) → **Needs Correction**.
4. Maps link missing → append request to customer message, set risk to Medium.
5. Never guess or invent location data.

## Execution

Call `execution/validate_location.py`.

## What to do when location is missing or unclear

- Send `location_request` message (bilingual).
- Set status to **Needs Correction** or **High Risk / Do Not Pack** depending on severity.
- Do not pack until full address + maps link are received and confirmed.

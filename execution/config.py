"""
config.py  -  Layer 3 (Execution)

Loads the project's reference data (delivery fees, product catalogue, WhatsApp
templates) from the data/ folder so every script reads from one source of truth.

Edit the JSON files in data/, not this file. This module just loads them.
"""

import json
from pathlib import Path

# data/ lives one level up from execution/
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# UAE mobile rules used across the project. Edit here if your carrier set changes.
# A valid number is the carrier prefix followed by 7 more digits = 10 digits total,
# e.g. 0501234567. We also accept the +971 / 971 international form.
VALID_UAE_PREFIXES = ["050", "051", "052", "055", "056", "057", "058"]
UAE_MOBILE_LENGTH = 10  # national form starting with 0, e.g. 0501234567

# Payment methods and which ones need documentary proof before dispatch.
PAYMENT_METHODS = ["Cash on Delivery", "Bank Transfer", "Card"]
PROOF_REQUIRED_METHODS = ["Bank Transfer", "Card"]  # COD is collected on delivery

# Operational statuses the verifier can return.
STATUS_VERIFIED = "Verified"
STATUS_AWAITING = "Awaiting Confirmation"
STATUS_CORRECTION = "Needs Correction"
STATUS_BLOCK = "High Risk / Do Not Pack"

# The 13 mandatory fields, in order.
MANDATORY_FIELDS = [
    "customer_name", "phone", "emirate", "area", "address",
    "product", "colour", "quantity", "unit_price", "delivery_fee",
    "total", "payment_method", "payment_status",
]


def _load(filename):
    with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


def load_delivery_fees():
    return _load("delivery_fees.json")


def load_catalogue():
    return _load("product_catalogue.json")


def load_templates():
    return _load("whatsapp_templates.json")["templates"]

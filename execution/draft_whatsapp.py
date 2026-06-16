"""
draft_whatsapp.py  -  Layer 3 (Execution)

Fills a named WhatsApp template from data/whatsapp_templates.json with order
fields. Pure string templating, no AI, so the wording is consistent every time.
"""

from config import load_templates


def draft_message(template_name: str, fields: dict) -> dict:
    """Return {ok, message, reason}. Missing placeholders are reported, not guessed."""
    templates = load_templates()
    if template_name not in templates:
        return {"ok": False, "message": "",
                "reason": f"Template '{template_name}' not found. Available: {', '.join(templates)}."}

    template = templates[template_name]
    try:
        message = template.format(**fields)
    except KeyError as missing:
        return {"ok": False, "message": "",
                "reason": f"Template '{template_name}' needs field {missing} which was not provided."}

    return {"ok": True, "message": message, "reason": "Message drafted."}


if __name__ == "__main__":
    sample = {
        "customer_name": "Fatima Al Marri", "product": "Gold Layered Chain Necklace",
        "colour": "Gold", "quantity": 1, "unit_price": 89, "area": "JVC",
        "emirate": "Dubai", "delivery_fee": 15, "total": 104,
    }
    print(draft_message("confirm_order", sample)["message"])

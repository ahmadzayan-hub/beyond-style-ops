"""
generate_whatsapp_message.py  -  Layer 3 (Execution)

Generates bilingual (English + simplified Gulf Arabic) WhatsApp messages
for every verification scenario.

Message types:
  confirm_order          - awaiting customer CONFIRM reply
  correction_fee         - fee / total updated, needs re-confirmation
  payment_proof_request  - Bank Transfer / Card needs screenshot
  phone_invalid          - cannot identify a valid UAE number
  location_request       - missing or unclear address / maps link
  dispatch_confirmed     - order verified, going to courier

This script returns text only. It never sends messages.
"""

_MAPS_PLACEHOLDER    = "[Share your Google Maps / live location here]"
_MAPS_PLACEHOLDER_AR = "[شارك لوكيشن Google Maps أو اللوكيشن المباشر هنا]"

TEMPLATES = {
    "confirm_order": {
        "en": (
            "Hi {customer_name}, thanks for your order with Beyond Style UAE! 🌟\n\n"
            "Before we pack, please confirm:\n\n"
            "📱 Mobile: {phone} — can receive courier calls\n"
            "📍 Address: {address}, {area}, {emirate}\n"
            "🗺 Location: {maps_link}\n"
            "🛍 Product: {product}{colour_line} × {quantity}\n"
            "💰 Total: AED {total} (AED {unit_price} × {quantity} + AED {delivery_fee} delivery)\n\n"
            "We'll hold your item for 24 hours.\n"
            "Please reply CONFIRM if everything is correct, or send any update needed.\n\n"
            "Thanks, Beyond Style UAE 💛"
        ),
        "ar": (
            "هلا {customer_name}، شكراً لطلبك من Beyond Style UAE! 🌟\n\n"
            "قبل ما نجهز الطلب، ممكن تأكدين/تأكد:\n\n"
            "📱 رقم الموبايل: {phone} — يستقبل اتصال المندوب\n"
            "📍 العنوان: {address}, {area}, {emirate}\n"
            "🗺 اللوكيشن: {maps_link}\n"
            "🛍 المنتج: {product}{colour_line_ar} × {quantity}\n"
            "💰 المبلغ: AED {total} (AED {unit_price} × {quantity} + AED {delivery_fee} توصيل)\n\n"
            "بنحجز القطعة لك لمدة 24 ساعة.\n"
            "يرجى الرد بكلمة CONFIRM إذا كل التفاصيل صحيحة، أو إرسال أي تعديل.\n\n"
            "شكراً، Beyond Style UAE 💛"
        ),
    },
    "correction_fee": {
        "en": (
            "Hi {customer_name}, thanks for your patience 🙏\n\n"
            "The delivery fee for {area}, {emirate} is AED {delivery_fee}.\n"
            "Your updated total: AED {total} "
            "(AED {unit_price} × {quantity} + AED {delivery_fee} delivery).\n\n"
            "Please reply CONFIRM to proceed with the updated total.\n\n"
            "Beyond Style UAE 💛"
        ),
        "ar": (
            "هلا {customer_name}، شكراً لصبرك 🙏\n\n"
            "رسوم التوصيل لـ {area}, {emirate} هي AED {delivery_fee}.\n"
            "المبلغ الجديد: AED {total} "
            "(AED {unit_price} × {quantity} + AED {delivery_fee} توصيل).\n\n"
            "يرجى الرد بكلمة CONFIRM للمتابعة.\n\n"
            "Beyond Style UAE 💛"
        ),
    },
    "payment_proof_request": {
        "en": (
            "Hi {customer_name}, your order is reserved! 🛍\n\n"
            "Product: {product}{colour_line} × {quantity}\n"
            "Total: AED {total}\n\n"
            "As payment is by {payment_method}, please send a screenshot of your "
            "transfer of AED {total} to release your order for delivery.\n\n"
            "We'll hold it for 24 hours.\n"
            "Beyond Style UAE 💛"
        ),
        "ar": (
            "هلا {customer_name}، طلبك محجوز! 🛍\n\n"
            "المنتج: {product}{colour_line_ar} × {quantity}\n"
            "المبلغ: AED {total}\n\n"
            "بما إن الدفع عن طريق {payment_method}، يرجى إرسال صورة التحويل "
            "بقيمة AED {total} حتى نرسل طلبك للتوصيل.\n\n"
            "بنحجزه لك 24 ساعة.\n"
            "Beyond Style UAE 💛"
        ),
    },
    "phone_invalid": {
        "en": (
            "Hi, this is Beyond Style UAE 👋\n\n"
            "We couldn't verify a valid UAE mobile number for your delivery.\n"
            "Could you please reply with your correct number? (e.g. 05X XXX XXXX)\n\n"
            "The courier needs a UAE number to reach you on delivery day.\n"
            "Beyond Style UAE 💛"
        ),
        "ar": (
            "هلا، معك فريق Beyond Style UAE 👋\n\n"
            "ما قدرنا نتحقق من رقم موبايل إماراتي صالح للتوصيل.\n"
            "ممكن ترسل/ترسلين رقمك الصحيح؟ (مثال: 05X XXX XXXX)\n\n"
            "المندوب يحتاج رقم إماراتي للتواصل معك يوم التوصيل.\n"
            "Beyond Style UAE 💛"
        ),
    },
    "location_request": {
        "en": (
            "Hi {customer_name}, thanks for your order! 🌟\n\n"
            "To make sure the courier can find you, please:\n"
            "1. Send your full address (building/villa number, street, landmark)\n"
            "2. Share your Google Maps location or WhatsApp live location\n\n"
            "Beyond Style UAE 💛"
        ),
        "ar": (
            "هلا {customer_name}، شكراً لطلبك! 🌟\n\n"
            "عشان نضمن وصول المندوب، ممكن:\n"
            "1. ترسل/ترسلين العنوان الكامل (رقم الفيلا/المبنى، الشارع، الميلاند)\n"
            "2. تشارك/تشاركين اللوكيشن على Google Maps أو اللوكيشن المباشر من واتساب\n\n"
            "Beyond Style UAE 💛"
        ),
    },
    "dispatch_confirmed": {
        "en": (
            "Hi {customer_name}, great news — your order is confirmed and being prepared "
            "for dispatch! 🎉\n\n"
            "🛍 {product}{colour_line} × {quantity}\n"
            "📍 {area}, {emirate}\n"
            "📱 Courier will contact you on {phone}\n\n"
            "You'll receive tracking details once handed to the courier.\n"
            "Thank you for choosing Beyond Style UAE! 💛"
        ),
        "ar": (
            "هلا {customer_name}، أخبار ممتازة — طلبك مؤكد وجارٍ تجهيزه للشحن! 🎉\n\n"
            "🛍 {product}{colour_line_ar} × {quantity}\n"
            "📍 {area}, {emirate}\n"
            "📱 المندوب سيتواصل معك على {phone}\n\n"
            "ستصلك تفاصيل التتبع بمجرد تسليمه للمندوب.\n"
            "شكراً لاختيارك Beyond Style UAE! 💛"
        ),
    },
}


def generate_whatsapp_message(message_type: str, fields: dict) -> dict:
    """
    Returns:
        type:     str
        en:       str   - English message
        ar:       str   - Gulf Arabic message
        combined: str   - EN + divider + AR
        ok:       bool
        reason:   str
    """
    if message_type not in TEMPLATES:
        return {
            "type": message_type, "en": "", "ar": "", "combined": "", "ok": False,
            "reason": (f"Unknown message type '{message_type}'. "
                       f"Use: {', '.join(TEMPLATES)}."),
        }

    f = _safe_fields(fields)
    tmpl = TEMPLATES[message_type]
    try:
        en = tmpl["en"].format(**f)
        ar = tmpl["ar"].format(**f)
    except KeyError as e:
        return {"type": message_type, "en": "", "ar": "", "combined": "",
                "ok": False, "reason": f"Missing template field: {e}"}

    combined = en + "\n\n" + "─" * 35 + "\n\n" + ar
    return {"type": message_type, "en": en, "ar": ar, "combined": combined,
            "ok": True, "reason": ""}


def _safe_fields(fields: dict) -> dict:
    d = dict(fields)
    defaults = {
        "customer_name": "Valued Customer",
        "phone":         "[phone]",
        "emirate":       "[emirate]",
        "area":          "[area]",
        "address":       "[address]",
        "maps_link":     _MAPS_PLACEHOLDER,
        "product":       "[product]",
        "colour":        "",
        "quantity":      "[qty]",
        "unit_price":    "[price]",
        "delivery_fee":  "[delivery fee]",
        "total":         "[total]",
        "payment_method": "Bank Transfer",
    }
    for k, v in defaults.items():
        if k not in d or d[k] is None or str(d[k]).strip() == "":
            d[k] = v

    colour = str(d.get("colour", "")).strip()
    d["colour_line"]    = f" ({colour})" if colour else ""
    d["colour_line_ar"] = f" ({colour})" if colour else ""

    if not str(d.get("maps_link", "")).strip():
        d["maps_link"] = _MAPS_PLACEHOLDER

    return d


if __name__ == "__main__":
    sample = {
        "customer_name": "Fatima Al Marri",
        "phone":         "0501234567",
        "emirate":       "Dubai",
        "area":          "JVC",
        "address":       "Villa 45, Al Manara St, near Emirates Mall",
        "product":       "Masha'Allah Bracelet",
        "colour":        "Gold",
        "quantity":      1,
        "unit_price":    79,
        "delivery_fee":  25,
        "total":         104,
        "payment_method": "Bank Transfer",
        "maps_link":     "",
    }
    for t in TEMPLATES:
        r = generate_whatsapp_message(t, sample)
        print(f"\n{'='*60}\n[{t.upper()}]\n{r['combined']}")

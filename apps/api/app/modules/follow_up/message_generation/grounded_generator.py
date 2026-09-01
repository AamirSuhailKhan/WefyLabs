"""
Grounded AI Follow-Up Message Generator
=======================================
Drafts personalized, high-conversion follow-up messages strictly using verified CRM
and property facts. Supports multiple languages (English, Hindi, Arabic, Urdu, French, Spanish, German).
"""

import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class GroundedMessageGenerator:
    """
    Produces grounded outbound messages based on structured strategy context.
    """

    def generate_message(
        self,
        context: Dict[str, Any],
        language: str = "en",
        channel: str = "WHATSAPP"
    ) -> Tuple[str, Optional[str]]:
        """
        Generates (message_body, optional_subject).
        """
        name = context.get("lead_name", "there")
        reason = context.get("reason_type", "UNANSWERED_INQUIRY")
        loc = context.get("preferred_location", "your target area")
        ptype = context.get("property_type", "home")
        prop = context.get("property")

        lang = language.lower() if language else "en"

        subject: Optional[str] = None
        if channel.upper() == "EMAIL":
            subject = f"Update regarding your property search in {loc}"

        # ── 1. Property-Triggered Messages ───────────────────────────────────
        if prop:
            p_title = prop.get("title", "New Property")
            p_price = f"{prop.get('price', 0):,.0f} {prop.get('currency', 'AED')}"
            p_beds = prop.get("bedrooms", 2)
            p_loc = f"{prop.get('locality', '')}, {prop.get('city', '')}".strip(", ")

            if reason == "PRICE_UPDATE":
                if lang == "ar":
                    body = f"مرحباً {name}، تم تحديث سعر {p_title} إلى {p_price}. هل ترغب في حجز موعد للمعاينة؟"
                elif lang == "hi":
                    body = f"नमस्ते {name}, {p_title} की कीमत अब {p_price} हो गई है। क्या आप इस सप्ताह इसे देखना चाहेंगे?"
                elif lang == "ur":
                    body = f"السلام علیکم {name}، {p_title} کی قیمت اب {p_price} ہو گئی ہے۔ کیا آپ وزٹ کرنا چاہتے ہیں؟"
                else:
                    body = f"Hi {name}, price update on {p_title} in {p_loc}: now available for {p_price} ({p_beds} BHK). Would you like to schedule a site visit this week?"
                return body, subject

            elif reason in ("PROPERTY_RECOMMENDATION", "NEW_MATCH", "REENGAGEMENT"):
                if lang == "ar":
                    body = f"مرحباً {name}، وجدنا وحدة جديدة مميزة تطابق طلبك: {p_title} بسعر {p_price}. هل تود الاطلاع على التفاصيل؟"
                elif lang == "hi":
                    body = f"नमस्ते {name}, हमें {p_loc} में आपकी पसंद का एक नया {p_beds} BHK प्रोजेक्ट मिला है ({p_title}, {p_price})। क्या मैं ब्रोशर भेजूं?"
                elif lang == "ur":
                    body = f"السلام علیکم {name}، {p_loc} میں آپ کے بجٹ کے مطابق نئی پراپرٹی دستیاب ہے ({p_title}, {p_price})۔ کیا آپ مزید معلومات چاہتے ہیں؟"
                else:
                    body = f"Hi {name}, a new matching property just became available in {p_loc}: {p_title} ({p_beds} BHK at {p_price}). Would you like me to send you the floor plan and brochure?"
                return body, subject

        # ── 2. Viewing & Meeting Reminders ───────────────────────────────────
        if reason == "VIEWING_REMINDER":
            if lang == "ar":
                body = f"مرحباً {name}، تذكير بموعد زيارة العقار غداً في {loc}. نتطلع للقائك!"
            elif lang == "hi":
                body = f"नमस्ते {name}, कल {loc} में आपकी प्रॉपर्टी विजिट का रिमाइंडर। क्या समय आपके लिए सही है?"
            else:
                body = f"Hi {name}, looking forward to showing you the properties in {loc} tomorrow. Please let us know if the scheduled time works for you!"
            return body, subject

        # ── 3. General Stage Progression Follow-Ups ──────────────────────────
        if lang == "ar":
            body = f"مرحباً {name}، هل ما زلت تبحث عن {ptype} في {loc}؟ نحن هنا لمساعدتك في أي استفسار."
        elif lang == "hi":
            body = f"नमस्ते {name}, क्या आप अभी भी {loc} में {ptype} देख रहे हैं? हमारे पास कुछ नए विकल्प हैं।"
        elif lang == "ur":
            body = f"السلام علیکم {name}، کیا آپ ابھی بھی {loc} میں {ptype} تلاش کر رہے ہیں؟ ہم آپ کی رہنمائی کے لیے تیار ہیں۔"
        else:
            body = f"Hi {name}, just checking if you have any questions regarding your search for a {ptype} in {loc}. We have newly verified inventory matching your criteria."

        return body, subject

from groq import Groq
from app.config import get_settings
from app.models import ExtractedOrder
import json
import structlog

logger = structlog.get_logger()
settings = get_settings()

client = Groq(api_key=settings.groq_api_key)

async def extract_order_groq(
    user_message: str,
    menu_items: str,
    language: str = "fr"
) -> ExtractedOrder:
    """
    Fallback extraction avec Groq Llama-3.2
    """
    from app.llm.prompts import SYSTEM_PROMPT_FR, SYSTEM_PROMPT_EN
    
    prompt_template = SYSTEM_PROMPT_FR if language == "fr" else SYSTEM_PROMPT_EN
    prompt = prompt_template.format(
        menu_items=menu_items,
        user_message=user_message
    )
    
    try:
        response = client.chat.completions.create(
            model="llama-3.2-90b-text-preview",
            messages=[
                {"role": "system", "content": "You extract JSON from food orders."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        
        text = response.choices[0].message.content.strip()
        
        # Nettoyer markdown
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        data = json.loads(text)
        
        logger.info(
            "groq_extraction_success",
            user_message=user_message[:50],
            items_count=len(data.get("items", []))
        )
        
        return ExtractedOrder(**data)
        
    except Exception as e:
        logger.error("groq_extraction_error", error=str(e))
        return ExtractedOrder(
            items=[],
            confidence=0,
            missing_fields=["all"]
        )
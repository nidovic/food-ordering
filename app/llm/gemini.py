import google.generativeai as genai
from app.config import get_settings
from app.models import ExtractedOrder
import json
import structlog

logger = structlog.get_logger()
settings = get_settings()

genai.configure(api_key=settings.gemini_api_key)
model = genai.GenerativeModel('gemini-2.0-flash-exp')

async def extract_order_gemini(
    user_message: str,
    menu_items: str,
    language: str = "fr"
) -> ExtractedOrder:
    """
    Extrait commande avec Gemini Flash
    
    Args:
        user_message: Message utilisateur
        menu_items: JSON des produits disponibles
        language: "fr" ou "en"
    
    Returns:
        ExtractedOrder avec extraction structurée
    """
    from app.llm.prompts import SYSTEM_PROMPT_FR, SYSTEM_PROMPT_EN
    
    prompt_template = SYSTEM_PROMPT_FR if language == "fr" else SYSTEM_PROMPT_EN
    prompt = prompt_template.format(
        menu_items=menu_items,
        user_message=user_message
    )
    
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                max_output_tokens=1024,
            )
        )
        
        # Extraire JSON de la réponse
        text = response.text.strip()
        # Retirer markdown si présent
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        # Parser JSON
        data = json.loads(text)
        
        logger.info(
            "gemini_extraction_success",
            user_message=user_message[:50],
            items_count=len(data.get("items", [])),
            confidence=data.get("confidence", 0)
        )
        
        return ExtractedOrder(**data)
        
    except json.JSONDecodeError as e:
        logger.error("gemini_json_parse_error", error=str(e), response=text)
        # Fallback: extraction vide
        return ExtractedOrder(
            items=[],
            confidence=0,
            missing_fields=["all"]
        )
    except Exception as e:
        logger.error("gemini_extraction_error", error=str(e))
        raise
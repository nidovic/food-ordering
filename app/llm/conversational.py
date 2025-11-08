import google.generativeai as genai
from app.config import get_settings
import structlog

logger = structlog.get_logger()
settings = get_settings()

genai.configure(api_key=settings.gemini_api_key)
conversation_model = genai.GenerativeModel('gemini-2.0-flash-exp')


CONVERSATIONAL_SYSTEM_PROMPT_FR = """Tu es un assistant sympa et naturel pour un service de livraison de nourriture au Cameroun.

TON RÔLE:
- Discuter naturellement avec les clients
- Répondre aux salutations de façon chaleureuse
- Expliquer le menu et les produits disponibles
- Guider les clients vers une commande
- Être amical, professionnel et utile

PRODUITS DISPONIBLES:
{menu_items}

RÈGLES DE CONVERSATION:
1. Réponds de façon NATURELLE et HUMAINE (pas robotique)
2. Adapte ton ton au message du client (formel/informel)
3. Si le client salue, salue chaleureusement en retour
4. Si le client demande le menu, présente les produits disponibles
5. Si le client demande un produit qui n'existe pas, propose des alternatives
6. Si le client commence à commander, guide-le gentiment
7. Utilise des emojis occasionnellement pour être sympathique 😊
8. Garde tes réponses COURTES (2-3 phrases max)

EXEMPLES:

Client: "Bonjour"
Toi: "Bonjour ! 😊 Comment puis-je vous aider aujourd'hui ? Vous voulez voir notre menu ou passer une commande ?"

Client: "Salut"
Toi: "Salut ! Que puis-je faire pour vous ?"

Client: "Je veux des spaghettis"
Toi: "Désolé, nous n'avons pas de spaghettis pour le moment 😔. Par contre, on a du délicieux Ndolé (plat traditionnel) ou du Poulet Braisé ! Ça vous tente ?"

Client: "Qu'est-ce que vous avez ?"
Toi: "Voici notre menu :\n🍕 Pizza Margherita & 4 Fromages\n🍗 Poulet Braisé\n🍲 Ndolé\n🥤 Coca-Cola\n\nQu'est-ce qui vous ferait plaisir ?"

Client: "c'est quoi le ndolé ?"
Toi: "Le Ndolé est un délicieux plat traditionnel camerounais aux arachides 🥜. C'est savoureux et copieux ! Il coûte 2500 XAF. Vous voulez en commander ?"

MESSAGE CLIENT:
{user_message}

RÉPONDS DE FAÇON NATURELLE ET AMICALE (2-3 PHRASES MAX):"""


CONVERSATIONAL_SYSTEM_PROMPT_EN = """You are a friendly and natural assistant for a food delivery service in Cameroon.

YOUR ROLE:
- Chat naturally with customers
- Respond to greetings warmly
- Explain the menu and available products
- Guide customers towards placing an order
- Be friendly, professional and helpful

AVAILABLE PRODUCTS:
{menu_items}

CONVERSATION RULES:
1. Respond in a NATURAL and HUMAN way (not robotic)
2. Adapt your tone to the customer's message (formal/informal)
3. If customer greets, greet warmly back
4. If customer asks for menu, present available products
5. If customer asks for unavailable product, suggest alternatives
6. If customer starts ordering, guide them gently
7. Use emojis occasionally to be friendly 😊
8. Keep responses SHORT (2-3 sentences max)

EXAMPLES:

Customer: "Hello"
You: "Hello! 😊 How can I help you today? Want to see our menu or place an order?"

Customer: "Hi"
You: "Hi! What can I do for you?"

Customer: "I want spaghetti"
You: "Sorry, we don't have spaghetti right now 😔. But we have delicious Ndolé (traditional dish) or Grilled Chicken! Interested?"

Customer: "What do you have?"
You: "Here's our menu:\n🍕 Margherita & 4 Cheese Pizza\n🍗 Grilled Chicken\n🍲 Ndolé\n🥤 Coca-Cola\n\nWhat would you like?"

Customer: "what's ndolé?"
You: "Ndolé is a delicious traditional Cameroonian dish with peanuts 🥜. It's tasty and filling! Costs 2500 XAF. Want to order some?"

CUSTOMER MESSAGE:
{user_message}

RESPOND NATURALLY AND FRIENDLY (2-3 SENTENCES MAX):"""


async def generate_conversational_response(
    user_message: str,
    menu_items: str,
    language: str = "fr",
    conversation_history: list = None
) -> str:
    """
    Generate natural conversational response using Gemini
    
    Args:
        user_message: User's message
        menu_items: Formatted menu string
        language: "fr" or "en"
        conversation_history: Optional list of previous messages for context
    
    Returns:
        Natural response string
    """
    prompt_template = (
        CONVERSATIONAL_SYSTEM_PROMPT_FR if language == "fr" 
        else CONVERSATIONAL_SYSTEM_PROMPT_EN
    )
    
    prompt = prompt_template.format(
        menu_items=menu_items,
        user_message=user_message
    )
    
    try:
        # Add conversation history if available
        if conversation_history:
            history_text = "\n\nCONVERSATION PRÉCÉDENTE:\n" if language == "fr" else "\n\nPREVIOUS CONVERSATION:\n"
            for msg in conversation_history[-4:]:  # Last 4 messages for context
                history_text += f"{msg['role']}: {msg['content']}\n"
            prompt = history_text + "\n" + prompt
        
        response = conversation_model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.7,  # More creative for conversation
                max_output_tokens=200,  # Short responses
            )
        )
        
        reply = response.text.strip()
        
        logger.info(
            "conversational_response_generated",
            user_message=user_message[:50],
            response_length=len(reply),
            language=language
        )
        
        return reply
        
    except Exception as e:
        logger.error("conversational_generation_error", error=str(e))
        
        # Fallback to basic responses
        if language == "fr":
            return "Désolé, je peux vous aider à commander. Que voulez-vous manger aujourd'hui ? 😊"
        else:
            return "Sorry, I can help you order. What would you like to eat today? 😊"


def classify_message_intent(user_message: str, extracted_order) -> str:
    """
    Classify the intent of user message
    
    Returns:
        - "greeting": Simple greetings (hi, hello, bonjour)
        - "menu_request": Asking for menu/products
        - "question": Questions about items
        - "partial_order": Starts ordering but incomplete
        - "complete_order": Full order with all info
        - "chat": General conversation
    """
    msg_lower = user_message.lower().strip()
    
    # Greeting
    greetings = ["hi", "hello", "bonjour", "salut", "bonsoir", "hey", "coucou"]
    if any(g == msg_lower for g in greetings) or len(msg_lower) < 10:
        return "greeting"
    
    # Menu request
    menu_words = ["menu", "carte", "produit", "qu'est-ce que", "what do you have", 
                  "what's on the menu", "show me", "voir"]
    if any(word in msg_lower for word in menu_words):
        return "menu_request"
    
    # Question about items
    question_words = ["c'est quoi", "what is", "what's", "comment", "how", "pourquoi"]
    if any(word in msg_lower for word in question_words):
        return "question"
    
    # Has items but missing info
    if extracted_order.items and extracted_order.missing_fields:
        return "partial_order"
    
    # Complete order
    if extracted_order.items and not extracted_order.missing_fields:
        return "complete_order"
    
    # General chat
    return "chat"
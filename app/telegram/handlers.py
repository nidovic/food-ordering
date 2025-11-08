from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from app.llm.gemini import extract_order_gemini
from app.llm.groq import extract_order_groq
from app.llm.conversational import generate_conversational_response, classify_message_intent
from app.api.spreeloop import api_client
from app.models import ExtractedOrder, CreateOrderRequest, PaymentGateway, OrderItemRequest, RestaurantOrder
from app.config import get_settings
import structlog
import json
from typing import Dict, Any

logger = structlog.get_logger()
settings = get_settings()

# Cache menu (refresh toutes les 5 min)
menu_cache = {"items": [], "timestamp": 0}

async def get_menu_formatted() -> str:
    """Retourne menu formaté pour prompt LLM"""
    import time
    
    if time.time() - menu_cache["timestamp"] > 300:  # 5 min
        items = await api_client.get_menu_items()
        menu_cache["items"] = items
        menu_cache["timestamp"] = time.time()
    
    # Format: "Pizza Margherita (5000 XAF) - menuItems/xxx"
    menu_str = "\n".join([
        f"{item.foodName or item.shortDescription} ({int(item.priceInXAF)} XAF) - {item.path}"
        for item in menu_cache["items"]
        if item.priceInXAF
    ])
    
    return menu_str


def get_conversation_history(context: ContextTypes.DEFAULT_TYPE) -> list:
    """Get conversation history from context"""
    if "conversation_history" not in context.user_data:
        context.user_data["conversation_history"] = []
    return context.user_data["conversation_history"]


def add_to_conversation_history(
    context: ContextTypes.DEFAULT_TYPE, 
    role: str, 
    content: str
):
    """Add message to conversation history"""
    history = get_conversation_history(context)
    history.append({"role": role, "content": content})
    # Keep only last 10 messages
    if len(history) > 10:
        context.user_data["conversation_history"] = history[-10:]


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler principal messages Telegram - VERSION CONVERSATIONNELLE
    """
    user_message = update.message.text
    user_id = update.effective_user.id
    username = update.effective_user.full_name or "Client"
    
    logger.info(
        "message_received",
        user_id=user_id,
        username=username,
        message=user_message[:100]
    )
    
    # Détecter langue (améliorer la détection)
    french_indicators = ["je", "mon", "ma", "le", "la", "bonjour", "salut", "veux", "voudrais"]
    english_indicators = ["i", "my", "the", "want", "would", "hello", "hi"]
    
    msg_lower = user_message.lower()
    french_count = sum(1 for w in french_indicators if w in msg_lower)
    english_count = sum(1 for w in english_indicators if w in msg_lower)
    
    language = "fr" if french_count >= english_count else "en"
    
    # Store language preference
    context.user_data["language"] = language
    
    # Get menu
    menu_str = await get_menu_formatted()
    
    # Get conversation history
    conversation_history = get_conversation_history(context)
    
    # Add user message to history
    add_to_conversation_history(context, "Client", user_message)
    
    # Extraction LLM avec fallback
    try:
        extracted = await extract_order_gemini(user_message, menu_str, language)
    except Exception as e:
        logger.warning("gemini_failed_fallback_groq", error=str(e))
        try:
            extracted = await extract_order_groq(user_message, menu_str, language)
        except:
            extracted = ExtractedOrder(
                items=[],
                confidence=0,
                missing_fields=["all"]
            )
    
    # Classifier l'intention du message
    intent = classify_message_intent(user_message, extracted)
    
    logger.info(
        "message_classified",
        intent=intent,
        items_count=len(extracted.items),
        confidence=extracted.confidence
    )
    
    # ===== CAS 1: SALUTATIONS ET CONVERSATION GÉNÉRALE =====
    if intent in ["greeting", "chat", "menu_request", "question"]:
        # Utiliser l'IA conversationnelle pour répondre naturellement
        reply = await generate_conversational_response(
            user_message=user_message,
            menu_items=menu_str,
            language=language,
            conversation_history=conversation_history
        )
        
        add_to_conversation_history(context, "Bot", reply)
        await update.message.reply_text(reply)
        return
    
    # ===== CAS 2: COMMANDE PARTIELLE (items détectés mais infos manquantes) =====
    if intent == "partial_order" and extracted.items:
        # Afficher ce qui a été compris
        items_preview = "\n".join([
            f"• {item.quantity}x {item.foodName}"
            for item in extracted.items
        ])
        
        if language == "fr":
            understood = f"Super ! J'ai compris :\n{items_preview}\n\n"
        else:
            understood = f"Great! I understood:\n{items_preview}\n\n"
        
        # Demander les infos manquantes de façon naturelle
        missing_fields_map = {
            "customer_name": ("votre nom", "your name"),
            "customer_phone": ("votre numéro de téléphone", "your phone number"),
            "delivery_address": ("l'adresse de livraison", "the delivery address"),
        }
        
        missing_items = []
        for field in extracted.missing_fields:
            if field in missing_fields_map:
                missing_items.append(
                    missing_fields_map[field][0] if language == "fr" 
                    else missing_fields_map[field][1]
                )
        
        if missing_items:
            if language == "fr":
                missing_text = ", ".join(missing_items[:-1])
                if len(missing_items) > 1:
                    missing_text += f" et {missing_items[-1]}"
                else:
                    missing_text = missing_items[0]
                
                reply = f"{understood}Pour finaliser, j'ai besoin de {missing_text}. Pouvez-vous me les donner ? 😊"
            else:
                missing_text = ", ".join(missing_items[:-1])
                if len(missing_items) > 1:
                    missing_text += f" and {missing_items[-1]}"
                else:
                    missing_text = missing_items[0]
                
                reply = f"{understood}To complete your order, I need {missing_text}. Can you provide them? 😊"
        else:
            reply = understood
        
        # Stocker la commande partielle
        context.user_data["pending_partial_order"] = extracted.model_dump()
        
        add_to_conversation_history(context, "Bot", reply)
        await update.message.reply_text(reply)
        return
    
    # ===== CAS 3: COMMANDE COMPLÈTE =====
    if intent == "complete_order" and extracted.items:
        await show_order_confirmation(update, context, extracted, language)
        return
    
    # ===== CAS 4: AUCUNE COMMANDE DÉTECTÉE (confidence très faible) =====
    # Utiliser l'IA conversationnelle pour une réponse naturelle
    reply = await generate_conversational_response(
        user_message=user_message,
        menu_items=menu_str,
        language=language,
        conversation_history=conversation_history
    )
    
    add_to_conversation_history(context, "Bot", reply)
    await update.message.reply_text(reply)


async def show_order_confirmation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    extracted: ExtractedOrder,
    language: str
):
    """Afficher le récapitulatif de commande avec boutons de confirmation"""
    
    items_summary = "\n".join([
        f"• {item.quantity}x {item.foodName}"
        for item in extracted.items
    ])
    
    # Calculate total price
    total_price = 0
    for item in extracted.items:
        # Find item in menu cache
        menu_item = next(
            (m for m in menu_cache["items"] if m.path == item.menuItemPath),
            None
        )
        if menu_item and menu_item.priceInXAF:
            total_price += item.quantity * menu_item.priceInXAF
    
    confirm_text = (
        f"📋 **Récapitulatif de commande**\n\n{items_summary}\n\n"
        f"👤 Nom: {extracted.customer_name}\n"
        f"📞 Téléphone: {extracted.customer_phone}\n"
        f"📍 Adresse: {extracted.delivery_address}\n"
        f"💰 Total: {int(total_price)} XAF\n"
        f"💵 Paiement: À la livraison\n\n"
        f"Tout est correct ?"
    ) if language == "fr" else (
        f"📋 **Order Summary**\n\n{items_summary}\n\n"
        f"👤 Name: {extracted.customer_name}\n"
        f"📞 Phone: {extracted.customer_phone}\n"
        f"📍 Address: {extracted.delivery_address}\n"
        f"💰 Total: {int(total_price)} XAF\n"
        f"💵 Payment: Cash on delivery\n\n"
        f"Everything correct?"
    )
    
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Confirmer" if language == "fr" else "✅ Confirm", 
                callback_data=f"confirm_{update.effective_user.id}"
            ),
            InlineKeyboardButton(
                "❌ Annuler" if language == "fr" else "❌ Cancel", 
                callback_data=f"cancel_{update.effective_user.id}"
            )
        ]
    ]
    
    # Stocker extracted dans context pour callback
    context.user_data["pending_order"] = extracted.model_dump()
    context.user_data["language"] = language
    
    await update.message.reply_text(
        confirm_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def handle_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Callback confirmation commande
    """
    query = update.callback_query
    await query.answer()
    
    action, user_id = query.data.split("_")
    language = context.user_data.get("language", "fr")
    
    if action == "cancel":
        reply = "Commande annulée. 😊 N'hésitez pas si vous changez d'avis !" if language == "fr" else "Order cancelled. 😊 Don't hesitate if you change your mind!"
        await query.edit_message_text(reply)
        return
    
    # Confirmer → Créer commande API
    extracted_data = context.user_data.get("pending_order")
    if not extracted_data:
        await query.edit_message_text(
            "Erreur: commande expirée. Veuillez recommencer." if language == "fr" 
            else "Error: order expired. Please start again."
        )
        return
    
    extracted = ExtractedOrder(**extracted_data)
    
    # Construire payload API
    order_items = []
    for item in extracted.items:
        # Trouver item dans menu cache
        menu_item = next(
            (m for m in menu_cache["items"] if m.path == item.menuItemPath),
            None
        )
        if not menu_item:
            logger.warning("menu_item_not_found", path=item.menuItemPath)
            continue
        
        order_items.append(OrderItemRequest(
            id=menu_item.path.split("/")[-1],
            count=item.quantity,
            priceInXAF=menu_item.priceInXAF,
            foodName=menu_item.foodName or menu_item.shortDescription,
            menuItemPath=menu_item.path
        ))
    
    if not order_items:
        await query.edit_message_text(
            "❌ Erreur: impossible de trouver les produits. Veuillez réessayer." if language == "fr"
            else "❌ Error: cannot find products. Please try again."
        )
        return
    
    # Get default place/restaurant
    place_path = f"places/{settings.spreeloop_default_place_id}" if hasattr(settings, 'spreeloop_default_place_id') else "places/default"
    restaurant_id = "default_restaurant"
    
    order_payload = CreateOrderRequest(
        deliveryCodeEnabled=True,
        deliveryTimeEnabled=False,
        packagingFeesEnabled=True,
        serviceFeesEnabled=True,
        isGuestCheckout=True,
        guestUserNumber=extracted.customer_phone,
        guestUserName=extracted.customer_name,
        selectedGateWay=PaymentGateway.CASH_TO_COURIER,
        creatorSource="CHAT_BOT_REGULAR",
        currencyCodeAlpha3="XAF",
        orders={
            restaurant_id: RestaurantOrder(
                selectedItems=order_items,
                placePath=place_path,
                takeAway=None  # Delivery
            )
        }
    )
    
    try:
        logger.info("creating_order", guest_name=extracted.customer_name)
        
        result = await api_client.create_order(
            order_payload,
            idempotency_key=f"{extracted.customer_phone}_{int(update.callback_query.message.date.timestamp())}"
        )
        
        if result.data and result.data.orderGroupPath:
            order_path = result.data.orderGroupPath
            
            success_msg = (
                f"✅ **Commande créée avec succès !**\n\n"
                f"📦 Numéro: `{order_path}`\n"
                f"💰 Paiement: À la livraison (cash)\n"
                f"🚚 Votre commande arrive bientôt !\n\n"
                f"Merci de votre confiance ! 😊"
            ) if language == "fr" else (
                f"✅ **Order created successfully!**\n\n"
                f"📦 Number: `{order_path}`\n"
                f"💰 Payment: Cash on delivery\n"
                f"🚚 Your order is on the way!\n\n"
                f"Thank you for your trust! 😊"
            )
            
            await query.edit_message_text(success_msg, parse_mode="Markdown")
            
        else:
            raise Exception("No order data in response")
        
    except Exception as e:
        logger.error("order_creation_failed", error=str(e))
        
        error_msg = (
            f"❌ **Erreur lors de la création de la commande**\n\n"
            f"Désolé, une erreur s'est produite. Veuillez réessayer dans quelques instants ou contactez-nous.\n\n"
            f"Erreur technique: {str(e)[:100]}"
        ) if language == "fr" else (
            f"❌ **Error creating order**\n\n"
            f"Sorry, an error occurred. Please try again in a few moments or contact us.\n\n"
            f"Technical error: {str(e)[:100]}"
        )
        
        await query.edit_message_text(error_msg, parse_mode="Markdown")
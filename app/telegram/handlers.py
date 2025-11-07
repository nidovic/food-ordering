from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from app.llm.gemini import extract_order_gemini
from app.llm.groq import extract_order_groq
from app.api.spreeloop import api_client
from app.models import ExtractedOrder, CreateOrderRequest, PaymentGateway
import structlog
import json

logger = structlog.get_logger()

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
        f"{item.foodName or item.shortDescription} ({item.priceInXAF} XAF) - {item.path}"
        for item in menu_cache["items"]
        if item.priceInXAF
    ])
    
    return menu_str

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler principal messages Telegram
    """
    user_message = update.message.text
    user_id = update.effective_user.id
    username = update.effective_user.full_name
    
    logger.info(
        "message_received",
        user_id=user_id,
        message=user_message[:100]
    )
    
    # Détecter langue (simple heuristic)
    language = "fr" if any(w in user_message.lower() for w in ["je", "mon", "bonjour"]) else "en"
    
    # Get menu
    menu_str = await get_menu_formatted()
    
    # Extraction LLM avec fallback
    try:
        extracted = await extract_order_gemini(user_message, menu_str, language)
    except Exception as e:
        logger.warning("gemini_failed_fallback_groq", error=str(e))
        extracted = await extract_order_groq(user_message, menu_str, language)
    
    # Cas 1: Pas de commande détectée (confidence < 0.3 ou items vide)
    if not extracted.items or extracted.confidence < 0.3:
        reply = (
            "Bonjour ! Je peux vous aider à commander. "
            "Dites-moi ce que vous voulez commander, par exemple: "
            "'2 pizzas margherita'"
        ) if language == "fr" else (
            "Hello! I can help you order. "
            "Tell me what you want, for example: "
            "'2 margherita pizzas'"
        )
        await update.message.reply_text(reply)
        return
    
    # Cas 2: Infos manquantes
    if extracted.missing_fields:
        missing = ", ".join(extracted.missing_fields)
        reply = f"Il me manque: {missing}. Pouvez-vous me les donner ?" if language == "fr" \
            else f"I need: {missing}. Can you provide them?"
        
        await update.message.reply_text(reply)
        return
    
    # Cas 3: Commande complète → Confirmer
    items_summary = "\n".join([
        f"• {item['quantity']}x {item['foodName']}"
        for item in extracted.items
    ])
    
    confirm_text = (
        f"📋 Récapitulatif:\n\n{items_summary}\n\n"
        f"👤 {extracted.customer_name}\n"
        f"📞 {extracted.customer_phone}\n"
        f"📍 {extracted.delivery_address}\n\n"
        f"Confirmer la commande ?"
    ) if language == "fr" else (
        f"📋 Summary:\n\n{items_summary}\n\n"
        f"👤 {extracted.customer_name}\n"
        f"📞 {extracted.customer_phone}\n"
        f"📍 {extracted.delivery_address}\n\n"
        f"Confirm order?"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Confirmer" if language == "fr" else "✅ Confirm", 
                               callback_data=f"confirm_{user_id}"),
            InlineKeyboardButton("❌ Annuler" if language == "fr" else "❌ Cancel", 
                               callback_data=f"cancel_{user_id}")
        ]
    ]
    
    # Stocker extracted dans context pour callback
    context.user_data["pending_order"] = extracted.model_dump()
    context.user_data["language"] = language
    
    await update.message.reply_text(
        confirm_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
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
        reply = "Commande annulée." if language == "fr" else "Order cancelled."
        await query.edit_message_text(reply)
        return
    
    # Confirmer → Créer commande API
    extracted_data = context.user_data.get("pending_order")
    if not extracted_data:
        await query.edit_message_text("Erreur: commande expirée." if language == "fr" else "Error: order expired.")
        return
    
    extracted = ExtractedOrder(**extracted_data)
    
    # Construire payload API
    order_items = []
    for item in extracted.items:
        # Trouver item dans menu cache
        menu_item = next(
            (m for m in menu_cache["items"] if m.path == item["menuItemPath"]),
            None
        )
        if not menu_item:
            continue
        
        order_items.append({
            "id": menu_item.path.split("/")[-1],
            "count": item["quantity"],
            "priceInXAF": menu_item.priceInXAF,
            "foodName": menu_item.foodName or menu_item.shortDescription,
            "menuItemPath": menu_item.path
        })
    
    # Récupérer restaurant_id (supposons premier item)
    restaurant_id = "default_restaurant"  # À ajuster selon logique
    place_path = "restaurants/default"  # À ajuster
    
    order_payload = CreateOrderRequest(
        deliveryCodeEnabled=True,
        isGuestCheckout=True,
        guestUserNumber=extracted.customer_phone,
        guestUserName=extracted.customer_name,
        selectedGateWay=PaymentGateway.CASH_TO_COURIER,
        creatorSource="CHAT_BOT_REGULAR",
        currencyCodeAlpha3="XAF",
        orders={
            restaurant_id: {
                "selectedItems": order_items,
                "placePath": place_path,
                "takeAway": None  # Delivery
            }
        }
    )
    
    try:
        result = await api_client.create_order(order_payload)
        
        order_path = result.get("data", {}).get("orderGroupPath", "N/A")
        
        success_msg = (
            f"✅ Commande créée !\n\n"
            f"📦 Numéro: {order_path}\n"
            f"💰 Paiement: À la livraison\n\n"
            f"Merci ! Votre commande arrive bientôt."
        ) if language == "fr" else (
            f"✅ Order created!\n\n"
            f"📦 Number: {order_path}\n"
            f"💰 Payment: On delivery\n\n"
            f"Thank you! Your order is on the way."
        )
        
        await query.edit_message_text(success_msg)
        
    except Exception as e:
        logger.error("order_creation_failed", error=str(e))
        
        error_msg = (
            "❌ Erreur lors de la création de la commande. "
            "Veuillez réessayer."
        ) if language == "fr" else (
            "❌ Error creating order. Please try again."
        )
        
        await query.edit_message_text(error_msg)
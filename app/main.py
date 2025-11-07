from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from app.config import get_settings
from app.telegram.handlers import handle_message, handle_confirm_callback
from app.utils.logger import setup_logging
import structlog

# Setup
setup_logging()
logger = structlog.get_logger()
settings = get_settings()

app = FastAPI(title="Food Ordering Bot")

# Telegram Application
telegram_app = Application.builder().token(settings.telegram_bot_token).build()

# Handlers
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
telegram_app.add_handler(CallbackQueryHandler(handle_confirm_callback))

@app.on_event("startup")
async def startup():
    """Initialize bot"""
    await telegram_app.initialize()
    await telegram_app.start()
    logger.info("bot_started")

@app.on_event("shutdown")
async def shutdown():
    """Cleanup"""
    await telegram_app.stop()
    await telegram_app.shutdown()
    from app.api.spreeloop import api_client
    await api_client.close()
    logger.info("bot_stopped")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/webhook")
async def webhook(request: Request):
    """Telegram webhook endpoint"""
    try:
        data = await request.json()
        update = Update.de_json(data, telegram_app.bot)
        await telegram_app.process_update(update)
        
        logger.info(
            "webhook_processed",
            update_id=update.update_id
        )
        
        return {"ok": True}
        
    except Exception as e:
        logger.error("webhook_error", error=str(e))
        return {"ok": False, "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
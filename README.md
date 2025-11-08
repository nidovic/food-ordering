---
title: Food Ordering Bot
emoji: 🍕
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# 🤖 Food Ordering Bot - Telegram Chatbot

Intelligent chatbot for food ordering in Cameroon via Telegram, with Natural Language Processing (French/English) and Spreeloop API integration.

## ✨ Features

- 🧠 **Advanced NLP**: Order extraction with Google Gemini 2.0 Flash + Groq fallback
- 🌍 **Multilingual**: French + English (automatic detection)
- 📦 **Complete Management**: Dynamic menu, confirmation, API order creation
- 💰 **Payment**: Cash on delivery
- 🚀 **Production-ready**: Structured logs, caching, error handling

## 🏗️ Architecture

```
User (Telegram) 
    ↓
FastAPI Webhook
    ↓
LLM (Gemini/Groq) → Extract order JSON
    ↓
Match items to Menu (API)
    ↓
Confirmation buttons
    ↓
Spreeloop API → Create order
```

## ⚙️ Configuration

**Required secrets** (configure in Space Settings → Repository secrets):

```bash
TELEGRAM_BOT_TOKEN=your_telegram_token
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
SPREELOOP_API_URL=https://your-api-url
SPREELOOP_API_TOKEN=your_bearer_token
SPREELOOP_DEFAULT_PLACE_ID=place_123
FIREBASE_CREDENTIALS_JSON={}
ENVIRONMENT=production
LOG_LEVEL=INFO
```

## 🚀 Setup Webhook

After Space is running, configure Telegram webhook:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook?url=https://huggingface.co/spaces/YOUR_USERNAME/food-ordering-bot/webhook"
```

Or use the direct Space URL:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook?url=https://YOUR_USERNAME-food-ordering-bot.hf.space/webhook"
```

## 📱 Usage

### User Commands

- **Order**: Just type what you want
  - Example FR: `"2 pizzas margherita et 1 coca"`
  - Example EN: `"I want 2 grilled chicken"`
- **Menu**: `/menu` - View available products

### Conversation Flow

1. User: "je veux 2 pizza margherita"
2. Bot: Extracts items + asks for missing info
3. User: "Jean Dupont, 675123456, Yaoundé"
4. Bot: Shows summary + Confirm/Cancel buttons
5. User: Clicks "Confirm"
6. Bot: Creates order via API → Shows order number

## 🏥 Health Check

Visit `/health` endpoint to check bot status:

```
https://YOUR_USERNAME-food-ordering-bot.hf.space/health
```

Expected response:
```json
{
  "status": "healthy",
  "bot": "running",
  "api": "connected"
}
```

## 📊 Monitoring

View logs in **Space → Logs** tab:

| Event | Description |
|-------|-------------|
| `bot_started` | Bot successfully started |
| `webhook_processed` | User message received |
| `gemini_extraction_success` | NLP extraction successful |
| `order_created` | Order created via API |
| `*_error` | Error to investigate |

## 🛠️ Tech Stack

- **Backend**: FastAPI (Python 3.11)
- **LLM**: Google Gemini 2.0 Flash + Groq Llama 3.2
- **Bot**: python-telegram-bot 20.7
- **API**: Spreeloop (Google API Gateway)
- **Hosting**: Hugging Face Spaces (Docker)

## 🔧 Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run locally
python -m app.main
```

## 🐛 Troubleshooting

### Bot not responding?

1. Check webhook configuration:
```bash
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

2. Verify Space is running (green status)

3. Check logs for errors in Space → Logs

### "Application startup failed"?

- Verify all secrets are configured
- Check logs for missing environment variables
- Ensure Telegram token is valid

### "gemini_json_parse_error"?

- Normal occasionally - Groq fallback activates automatically
- Check subsequent logs for `groq_extraction_success`

## 📄 License

MIT

## 🇨🇲 Made with ❤️ for Cameroon

---

**Need help?** Check the [documentation](https://huggingface.co/docs/hub/spaces) or open an issue.
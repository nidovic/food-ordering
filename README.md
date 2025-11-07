# Food Ordering Bot

A Telegram bot for food ordering built with FastAPI, Gemini LLM, and Groq as fallback.

## Features

- Telegram bot integration
- LLM-powered responses using Gemini (primary) and Groq (fallback)
- FastAPI webhook handling
- Structured logging
- Docker support
- Render deployment

## Setup

1. Clone the repository
2. Copy `.env.example` to `.env` and fill in your API keys
3. Install dependencies: `pip install -r requirements.txt`
4. Run the app: `uvicorn app.main:app --reload`

## Deployment

- Docker: `docker build -t food-bot . && docker run food-bot`
- Render: Use `render.yaml` for configuration

## Structure

- `app/main.py`: FastAPI app and webhook
- `app/config.py`: Environment variables
- `app/models.py`: Pydantic schemas
- `app/llm/`: LLM integrations (Gemini, Groq, prompts)
- `app/api/`: External API clients
- `app/telegram/`: Telegram handlers
- `app/utils/`: Utilities like logging

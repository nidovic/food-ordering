import pytest
from unittest.mock import AsyncMock, patch
from app.llm.gemini import extract_order_gemini
from app.llm.groq import extract_order_groq
from app.models import ExtractedOrder

# Mock menu data
MOCK_MENU = """
Pizza Margherita (5000 XAF) - menuItems/pizza-margherita
Burger Classic (7000 XAF) - menuItems/burger-classic
Pasta Carbonara (6000 XAF) - menuItems/pasta-carbonara
Salad César (4000 XAF) - menuItems/salad-cesar
"""

@pytest.mark.asyncio
async def test_extract_order_gemini_simple_order():
    """Test simple order extraction with Gemini"""
    user_message = "Je veux 2 pizzas margherita"
    language = "fr"

    # Mock the model response
    mock_response = AsyncMock()
    mock_response.text = '{"items":[{"foodName":"Pizza Margherita","quantity":2,"menuItemPath":"menuItems/pizza-margherita"}],"confidence":0.9,"missing_fields":[]}'

    with patch('app.llm.gemini.model.generate_content', return_value=mock_response):
        result = await extract_order_gemini(user_message, MOCK_MENU, language)

    assert isinstance(result, ExtractedOrder)
    assert len(result.items) == 1
    assert result.items[0]['foodName'] == "Pizza Margherita"
    assert result.items[0]['quantity'] == 2
    assert result.confidence == 0.9

@pytest.mark.asyncio
async def test_extract_order_gemini_multiple_items():
    """Test multiple items in order"""
    user_message = "1 burger et 1 salade césar"
    language = "fr"

    mock_response = AsyncMock()
    mock_response.text = '''{
        "items":[
            {"foodName":"Burger Classic","quantity":1,"menuItemPath":"menuItems/burger-classic"},
            {"foodName":"Salad César","quantity":1,"menuItemPath":"menuItems/salad-cesar"}
        ],
        "confidence":0.8,
        "missing_fields":[]
    }'''

    with patch('app.llm.gemini.model.generate_content', return_value=mock_response):
        result = await extract_order_gemini(user_message, MOCK_MENU, language)

    assert len(result.items) == 2
    assert result.confidence == 0.8

@pytest.mark.asyncio
async def test_extract_order_gemini_missing_info():
    """Test when customer info is missing"""
    user_message = "2 pizzas"
    language = "fr"

    mock_response = AsyncMock()
    mock_response.text = '{"items":[{"foodName":"Pizza Margherita","quantity":2,"menuItemPath":"menuItems/pizza-margherita"}],"confidence":0.7,"missing_fields":["customer_phone","delivery_address"]}'

    with patch('app.llm.gemini.model.generate_content', return_value=mock_response):
        result = await extract_order_gemini(user_message, MOCK_MENU, language)

    assert len(result.items) == 1
    assert "customer_phone" in result.missing_fields
    assert "delivery_address" in result.missing_fields

@pytest.mark.asyncio
async def test_extract_order_gemini_no_order():
    """Test when no order is detected"""
    user_message = "Bonjour, comment allez-vous?"
    language = "fr"

    mock_response = AsyncMock()
    mock_response.text = '{"items":[],"confidence":0.0,"missing_fields":[]}'

    with patch('app.llm.gemini.model.generate_content', return_value=mock_response):
        result = await extract_order_gemini(user_message, MOCK_MENU, language)

    assert len(result.items) == 0
    assert result.confidence == 0.0

@pytest.mark.asyncio
async def test_extract_order_groq_fallback():
    """Test Groq fallback extraction"""
    user_message = "I want 1 pasta carbonara"
    language = "en"

    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = '{"items":[{"foodName":"Pasta Carbonara","quantity":1,"menuItemPath":"menuItems/pasta-carbonara"}],"confidence":0.85,"missing_fields":[]}'

    with patch('app.llm.groq.client.chat.completions.create', return_value=mock_response):
        result = await extract_order_groq(user_message, MOCK_MENU, language)

    assert len(result.items) == 1
    assert result.items[0]['foodName'] == "Pasta Carbonara"
    assert result.confidence == 0.85

# Add more test cases as needed...

@pytest.mark.asyncio
async def test_extract_order_gemini_json_parse_error():
    """Test handling of invalid JSON response"""
    user_message = "2 burgers"
    language = "fr"

    mock_response = AsyncMock()
    mock_response.text = 'Invalid JSON response'

    with patch('app.llm.gemini.model.generate_content', return_value=mock_response):
        result = await extract_order_gemini(user_message, MOCK_MENU, language)

    # Should return empty extraction on parse error
    assert len(result.items) == 0
    assert result.confidence == 0
    assert result.missing_fields == ["all"]

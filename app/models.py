from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

class PaymentGateway(str, Enum):
    CASH_TO_COURIER = "CASH_TO_COURIER_PAYMENT"
    MTN_MOMO = "MTN_MOMO"
    ORANGE_MONEY = "ORANGE_MONEY"

class ExtractedOrder(BaseModel):
    """Structure extraite par LLM"""
    items: List[Dict[str, Any]]  # [{foodName, quantity, menuItemPath}]
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    delivery_address: Optional[str] = None
    payment_method: PaymentGateway = PaymentGateway.CASH_TO_COURIER
    special_instructions: Optional[str] = None
    confidence: float = Field(ge=0, le=1)  # Confiance extraction
    missing_fields: List[str] = []  # Champs manquants

class OrderItem(BaseModel):
    id: str
    count: int
    priceInXAF: float
    foodName: str
    menuItemPath: str

class CreateOrderRequest(BaseModel):
    """Payload pour API Spreeloop"""
    deliveryCodeEnabled: bool = True
    deliveryTimeEnabled: bool = False
    packagingFeesEnabled: bool = True
    serviceFeesEnabled: bool = True
    promoCode: Optional[str] = None
    currencyCodeAlpha3: str = "XAF"
    isGuestCheckout: bool = True
    guestUserNumber: str
    guestUserName: str
    selectedGateWay: PaymentGateway
    mobileMoneyNumber: Optional[str] = None
    creatorSource: str = "CHAT_BOT_REGULAR"
    orders: Dict[str, Dict]  # {restaurant_id: {selectedItems, placePath}}
    orderDisplayName: Optional[str] = None

class BaseItem(BaseModel):
    """Menu item from API"""
    path: str
    shortDescription: str
    longDescription: Optional[str] = None
    imagePath: Optional[str] = None
    isAvailable: bool
    isVisible: bool
    foodName: Optional[str] = None
    foodType: Optional[str] = None
    priceInXAF: Optional[float] = None
    isVegetarian: bool = False
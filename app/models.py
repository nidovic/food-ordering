from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


# ============= ENUMS =============

class PaymentGateway(str, Enum):
    """Supported payment methods"""
    STRIPE = "STRIPE"
    MTN_MOMO = "MTN_MOMO"
    ORANGE_MONEY = "ORANGE_MONEY"
    CASH_TO_COURIER = "CASH_TO_COURIER_PAYMENT"
    CASH_TO_PARTNER = "CASH_TO_PARTNER_PAYMENT"


class CreatorSource(str, Enum):
    """Order creation source"""
    CHATBOT = "CHAT_BOT_REGULAR"
    APP_CUSTOMER = "APP_CUSTOMERS_REGULAR"


class BaseItemType(str, Enum):
    """Menu item type"""
    MENU_ITEM = "BASE_ITEM_TYPE_MENU_ITEM"
    RESERVATION = "BASE_ITEM_TYPE_RESERVATION_ITEM"


# ============= LLM EXTRACTION =============

class ExtractedOrderItem(BaseModel):
    """Item extracted by LLM"""
    foodName: str
    quantity: int = Field(gt=0)
    menuItemPath: Optional[str] = None  # Filled after matching


class ExtractedOrder(BaseModel):
    """Structured extraction from user message"""
    items: List[ExtractedOrderItem]
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    delivery_address: Optional[str] = None
    payment_method: PaymentGateway = None
    special_instructions: Optional[str] = None
    confidence: float = Field(ge=0, le=1, default=0.5)
    missing_fields: List[str] = Field(default_factory=list)
    
    @field_validator('customer_phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Validate Cameroon phone format"""
        if v and not v.startswith('+237'):
            # Add +237 if missing
            if v.startswith('237'):
                return '+' + v
            elif v.startswith('6') or v.startswith('2'):
                return '+237' + v
        return v


# ============= SPREELOOP API - MENU =============

class CookingTime(BaseModel):
    """Cooking time range"""
    min: int
    max: int


class BaseItem(BaseModel):
    """Menu item (proto BaseItem)"""
    path: str
    shortDescription: str
    longDescription: Optional[str] = None
    imagePath: Optional[str] = None
    isAvailable: bool
    isVisible: bool
    categoriesPaths: List[str] = Field(default_factory=list)
    foodName: Optional[str] = None
    foodType: Optional[str] = None
    numberOfPerson: Optional[int] = None
    priceInXAF: Optional[float] = None
    nonDiscountedPriceInXAF: Optional[float] = None
    isVegetarian: bool = False
    cookingTimeInMinutes: Optional[CookingTime] = None
    packageFee: Optional[float] = None
    baseItemType: str = "BASE_ITEM_TYPE_MENU_ITEM"
    
    def display_name(self) -> str:
        """Display name for UI"""
        return self.foodName or self.shortDescription
    
    def display_price(self) -> str:
        """Formatted price"""
        if self.priceInXAF:
            return f"{int(self.priceInXAF)} XAF"
        return "Prix non disponible"


# ============= SPREELOOP API - ORDER =============

class OrderItemRequest(BaseModel):
    """Item in order"""
    id: str  # Path ID (e.g., "item_456")
    count: int
    priceInXAF: float
    foodName: str
    menuItemPath: str


class TakeAwayInfo(BaseModel):
    """Takeaway/delivery info"""
    arrivalDateTime: Optional[str] = None  # ISO format


class RestaurantOrder(BaseModel):
    """Order for a restaurant"""
    selectedItems: List[OrderItemRequest]
    placePath: str
    takeAway: Optional[TakeAwayInfo] = None


class CreateOrderRequest(BaseModel):
    """Order creation payload for API"""
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
    creatorSource: CreatorSource = CreatorSource.CHATBOT
    orders: Dict[str, RestaurantOrder]  # {restaurant_id: order}
    orderDisplayName: Optional[str] = None


class OrderResponse(BaseModel):
    """Order creation response data"""
    orderGroupPath: str
    paymentPath: str
    createdAt: datetime


class CreateOrderApiResponse(BaseModel):
    """Complete API response"""
    data: Optional[OrderResponse] = None
    error: Optional[Dict[str, Any]] = None
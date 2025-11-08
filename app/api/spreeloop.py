"""Spreeloop API client with mock mode for development"""

import httpx
from app.config import get_settings
from app.models import BaseItem, CreateOrderRequest, CreateOrderApiResponse
from typing import List, Optional
from app.config import get_settings
from app.utils.logger import setup_logging
import structlog

# Setup
setup_logging()
logger = structlog.get_logger()
settings = get_settings()


class SpreeloopAPIError(Exception):
    """Custom exception for API errors"""
    pass


def get_mock_menu_items() -> List[BaseItem]:
    """
    Retourne menu items mock pour développement/test sans API
    
    Returns:
        List de 5 BaseItem mock (pizzas, poulet, coca, ndolé)
    """
    mock_items_data = [
        {
            "path": "menuItems/pizza_margherita",
            "shortDescription": "Pizza Margherita",
            "foodName": "Pizza Margherita",
            "longDescription": "Pizza classique tomate mozzarella basilic",
            "isAvailable": True,
            "isVisible": True,
            "categoriesPaths": ["categories/pizza"],
            "priceInXAF": 5000.0,
            "isVegetarian": True,
            "baseItemType": "BASE_ITEM_TYPE_MENU_ITEM"
        },
        {
            "path": "menuItems/pizza_4fromages",
            "shortDescription": "Pizza 4 Fromages",
            "foodName": "Pizza 4 Fromages",
            "longDescription": "Mozzarella, gorgonzola, chèvre, emmental",
            "isAvailable": True,
            "isVisible": True,
            "categoriesPaths": ["categories/pizza"],
            "priceInXAF": 6000.0,
            "isVegetarian": True,
            "baseItemType": "BASE_ITEM_TYPE_MENU_ITEM"
        },
        {
            "path": "menuItems/poulet_braise",
            "shortDescription": "Poulet Braisé",
            "foodName": "Poulet Braisé",
            "longDescription": "Poulet grillé sauce tomate épicée",
            "isAvailable": True,
            "isVisible": True,
            "categoriesPaths": ["categories/plats"],
            "priceInXAF": 3500.0,
            "isVegetarian": False,
            "baseItemType": "BASE_ITEM_TYPE_MENU_ITEM"
        },
        {
            "path": "menuItems/coca_cola",
            "shortDescription": "Coca-Cola",
            "foodName": "Coca-Cola",
            "longDescription": "Boisson gazeuse 33cl",
            "isAvailable": True,
            "isVisible": True,
            "categoriesPaths": ["categories/boissons"],
            "priceInXAF": 500.0,
            "isVegetarian": True,
            "baseItemType": "BASE_ITEM_TYPE_MENU_ITEM"
        },
        {
            "path": "menuItems/ndole",
            "shortDescription": "Ndolé",
            "foodName": "Ndolé",
            "longDescription": "Plat traditionnel camerounais aux arachides",
            "isAvailable": True,
            "isVisible": True,
            "categoriesPaths": ["categories/plats"],
            "priceInXAF": 2500.0,
            "isVegetarian": False,
            "baseItemType": "BASE_ITEM_TYPE_MENU_ITEM"
        }
    ]
    
    return [BaseItem(**item) for item in mock_items_data]


class SpreeloopAPI:
    """HTTP client for Spreeloop API Gateway"""
    
    def __init__(self):
        self.base_url = settings.spreeloop_api_url.rstrip('/')
        self.headers = {
            "Authorization": f"Bearer {settings.spreeloop_api_token}",
            "Content-Type": "application/json"
        }
        self.timeout = httpx.Timeout(30.0, connect=10.0)
        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True
        )
    
    async def get_menu_items(
        self,
        place_id: Optional[str] = None
    ) -> List[BaseItem]:
        """
        Fetch available menu items
        
        MODE DEVELOPMENT (ENVIRONMENT=development):
            - Returns 5 mock items (no API call)
            - Perfect for testing without real API
        
        MODE PRODUCTION (ENVIRONMENT=production):
            - Calls real Spreeloop API
            - Returns actual menu items
        
        Args:
            place_id: Restaurant ID (optional, uses default if None)
        
        Returns:
            List[BaseItem] filtered (available + visible + MENU_ITEM type)
        
        Raises:
            SpreeloopAPIError if API error (production mode only)
        """
        
        # 🔧 MODE MOCK pour développement
        if settings.environment == "development":
            logger.info(
                "dev_mode_using_mock_menu",
                items_count=5,
                mode="mock"
            )
            return get_mock_menu_items()
        
        # 🚀 MODE PRODUCTION - vraie API
        place = place_id or settings.spreeloop_default_place_id
        
        try:
            # TODO: Adjust endpoint according to actual API
            url = f"{self.base_url}/places/{place}/menu-items"
            
            logger.info("api_get_menu_start", place_id=place, url=url)
            
            response = await self.client.get(url, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            
            # Parse proto structure
            # Assuming: {"items": [...]}
            raw_items = data.get("items", [])
            
            # Parse to BaseItem
            items = []
            for raw in raw_items:
                try:
                    item = BaseItem(**raw)
                    items.append(item)
                except Exception as e:
                    logger.warning(
                        "item_parse_error",
                        error=str(e),
                        item_path=raw.get("path", "unknown")
                    )
            
            # Filter: available + visible + MENU_ITEM type
            available = [
                item for item in items
                if item.isAvailable
                and item.isVisible
                and item.baseItemType == "BASE_ITEM_TYPE_MENU_ITEM"
                and item.priceInXAF is not None
            ]
            
            logger.info(
                "api_get_menu_success",
                total=len(items),
                available=len(available),
                place_id=place
            )
            
            return available
            
        except httpx.HTTPStatusError as e:
            logger.error(
                "api_get_menu_http_error",
                status=e.response.status_code,
                detail=e.response.text[:500]
            )
            raise SpreeloopAPIError(f"HTTP {e.response.status_code}")
            
        except Exception as e:
            logger.error("api_get_menu_error", error=str(e))
            raise SpreeloopAPIError(str(e))
    
    async def create_order(
        self,
        order: CreateOrderRequest,
        idempotency_key: Optional[str] = None
    ) -> CreateOrderApiResponse:
        """
        Create order
        
        MODE DEVELOPMENT (ENVIRONMENT=development):
            - Returns mock order response
            - No real API call
        
        MODE PRODUCTION (ENVIRONMENT=production):
            - Creates real order via API
        
        Args:
            order: Validated CreateOrderRequest
            idempotency_key: Key to prevent duplicates (phone+timestamp)
        
        Returns:
            CreateOrderApiResponse with orderGroupPath
        
        Raises:
            SpreeloopAPIError if error (production mode only)
        """
        
        # 🔧 MODE MOCK pour développement
        if settings.environment == "development":
            from datetime import datetime
            from app.models import OrderResponse
            
            logger.info(
                "dev_mode_mock_order_created",
                mode="mock",
                guest_name=order.guestUserName,
                items_count=sum(
                    len(rest_order.selectedItems)
                    for rest_order in order.orders.values()
                )
            )
            
            # Mock response qui ressemble à la vraie
            mock_response = CreateOrderApiResponse(
                data=OrderResponse(
                    orderGroupPath="ordersGroups/mock_group_123/orders/mock_order_456",
                    paymentPath="payments/mock_payment_789",
                    createdAt=datetime.now()
                )
            )
            return mock_response
        
        # 🚀 MODE PRODUCTION - vraie API
        try:
            # TODO: Adjust endpoint according to actual API
            url = f"{self.base_url}/orders"
            
            headers = self.headers.copy()
            if idempotency_key:
                headers["Idempotency-Key"] = idempotency_key
            
            payload = order.model_dump(exclude_none=True, by_alias=True)
            
            logger.info(
                "api_create_order_start",
                guest_phone=order.guestUserNumber,
                items_count=sum(
                    len(rest_order.selectedItems)
                    for rest_order in order.orders.values()
                )
            )
            
            response = await self.client.post(
                url,
                headers=headers,
                json=payload,
                timeout=httpx.Timeout(60.0)  # Order creation can be slow
            )
            response.raise_for_status()
            
            data = response.json()
            result = CreateOrderApiResponse(**data)
            
            if result.data:
                logger.info(
                    "api_create_order_success",
                    order_path=result.data.orderGroupPath,
                    payment_path=result.data.paymentPath
                )
            elif result.error:
                logger.error("api_create_order_business_error", error=result.error)
                raise SpreeloopAPIError(f"Business error: {result.error}")
            
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(
                "api_create_order_http_error",
                status=e.response.status_code,
                detail=e.response.text[:500]
            )
            raise SpreeloopAPIError(
                f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            )
            
        except Exception as e:
            logger.error("api_create_order_error", error=str(e))
            raise SpreeloopAPIError(str(e))
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Singleton instance
api_client = SpreeloopAPI()
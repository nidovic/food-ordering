import httpx
from app.config import get_settings
from app.models import BaseItem, CreateOrderRequest
from typing import List
import structlog

logger = structlog.get_logger()
settings = get_settings()

class SpreeloopAPI:
    def __init__(self):
        self.base_url = settings.spreeloop_api_url
        self.headers = {
            "Authorization": f"Bearer {settings.spreeloop_api_token}",
            "Content-Type": "application/json"
        }
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def get_menu_items(self, place_id: str = None) -> List[BaseItem]:
        """
        Récupère tous les produits disponibles
        
        Args:
            place_id: ID du restaurant (optionnel)
        
        Returns:
            Liste des BaseItem disponibles
        """
        try:
            url = f"{self.base_url}/products"  # À ajuster selon API
            if place_id:
                url += f"?placeId={place_id}"
            
            response = await self.client.get(url, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            
            # Parser proto → Pydantic
            items = [BaseItem(**item) for item in data.get("items", [])]
            
            # Filtrer disponibles + visibles
            available = [
                item for item in items 
                if item.isAvailable and item.isVisible
            ]
            
            logger.info(
                "menu_items_fetched",
                total=len(items),
                available=len(available)
            )
            
            return available
            
        except httpx.HTTPStatusError as e:
            logger.error("api_get_menu_error", status=e.response.status_code)
            raise
        except Exception as e:
            logger.error("api_get_menu_error", error=str(e))
            raise
    
    async def create_order(self, order: CreateOrderRequest) -> dict:
        """
        Crée commande via API
        
        Args:
            order: CreateOrderRequest validé
        
        Returns:
            Response API {orderGroupPath, paymentPath, createdAt}
        """
        try:
            url = f"{self.base_url}/orders"  # À ajuster
            
            payload = order.model_dump(exclude_none=True)
            
            response = await self.client.post(
                url,
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            
            logger.info(
                "order_created",
                order_path=result.get("data", {}).get("orderGroupPath")
            )
            
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(
                "api_create_order_error",
                status=e.response.status_code,
                detail=e.response.text
            )
            raise
        except Exception as e:
            logger.error("api_create_order_error", error=str(e))
            raise
    
    async def close(self):
        await self.client.aclose()

# Singleton
api_client = SpreeloopAPI()
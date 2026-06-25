"""
Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Union
from decimal import Decimal


# ============================================================================
# REQUEST SCHEMAS
# ============================================================================

class SearchRequest(BaseModel):
    """Search intent request schema"""
    sport: Optional[str] = Field(None, description="Sport category (e.g., 'Hiking', 'Football')")
    category_level_1: Optional[str] = Field(None, description="Level 1 category (e.g., 'Footwear')")
    category_level_2: Optional[str] = Field(None, description="Level 2 category (e.g., 'Hiking Shoes')")
    keywords: List[str] = Field(default_factory=list, description="Search keywords")
    price_limit: Optional[float] = Field(None, description="Maximum price", gt=0)


class TaskArguments(BaseModel):
    """Task intent arguments"""
    activity: str = Field(..., description="Activity name (e.g., 'Golf', 'Hiking')")
    budget: Optional[float] = Field(None, description="Total budget", gt=0)
    query: Optional[str] = Field(None, description="Original user query for profile inference")


class CompareArguments(BaseModel):
    """Compare intent arguments"""
    products: List[str] = Field(..., min_items=2, description="Product IDs to compare")


class AlternativesArguments(BaseModel):
    """Alternatives intent arguments"""
    product: str = Field(..., description="Product ID to find alternatives for")
    query: Optional[str] = Field(None, description="Original user query for constraint extraction")


# ============================================================================
# AGENT REQUEST (Unified Endpoint)
# ============================================================================

class SearchIntent(BaseModel):
    """Search intent"""
    intent: Literal["search"] = "search"
    search_request: SearchRequest


class TaskIntent(BaseModel):
    """Task intent"""
    intent: Literal["task"] = "task"
    arguments: TaskArguments


class CompareIntent(BaseModel):
    """Compare intent"""
    intent: Literal["compare"] = "compare"
    arguments: CompareArguments


class AlternativesIntent(BaseModel):
    """Alternatives intent"""
    intent: Literal["alternatives"] = "alternatives"
    arguments: AlternativesArguments


# Union type for agent request
AgentRequest = Union[SearchIntent, TaskIntent, CompareIntent, AlternativesIntent]


# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================

class Product(BaseModel):
    """Product schema"""
    product_id: str
    name: str
    brand: Optional[str]
    price: float
    mrp: Optional[float]
    savings: Optional[float] = None         # mrp - price
    discount_percent: Optional[int] = None  # % off MRP
    sport: Optional[str] = None
    category_level_1: Optional[str]
    category_level_2: Optional[str]
    description: Optional[str]
    image_url: Optional[str]
    product_url: Optional[str]
    rating: Optional[float]
    review_count: Optional[int]
    similarity: Optional[float] = None           # Hybrid search score
    validation_confidence: Optional[float] = None # SLM product-type validation confidence
    profile_score: Optional[float] = None         # Deterministic user-profile match (kids/beginner)
    recommendation_score: Optional[float] = None   # SLM task-kit recommendation confidence (Phase 2)
    recommendation_decision: Optional[str] = None  # RECOMMENDED / ACCEPTABLE / NOT_RECOMMENDED (Phase 2)

    class Config:
        json_encoders = {
            Decimal: float
        }


class SearchResponse(BaseModel):
    """Search tool response"""
    type: Literal["search"] = "search"
    products: List[Product]
    total: int
    query: SearchRequest


class TaskItem(BaseModel):
    """
    One item in a task kit (e.g. 'Golf Clubs').
    
    recommended: the single best pick (auto-selected by score/budget).
    products:    full discovery list — all valid matches ranked by score,
                 so the user can browse and swap if they prefer another.
    """
    name: str
    mandatory: bool
    recommended: Optional[Product] = None  # Top-scored product
    products: List[Product] = Field(default_factory=list)  # Full ranked list
    budget_allocated: Optional[float] = None  # Cost of recommended pick


class TaskResponse(BaseModel):
    """Task tool response — activity-based product discovery"""
    type: Literal["task"] = "task"
    activity: str
    budget: Optional[float]
    budget_remaining: Optional[float] = None  # budget - total_cost
    total_cost: Optional[float] = None
    within_budget: Optional[bool] = None
    items: List[TaskItem]
    query: Optional[str] = None


class CompareResponse(BaseModel):
    """Compare tool response"""
    type: Literal["compare"] = "compare"
    products: List[Product]


class AlternativesResponse(BaseModel):
    """Alternatives tool response"""
    type: Literal["alternatives"] = "alternatives"
    source_product: Product
    products: List[Product]
    total: int


class ErrorResponse(BaseModel):
    """Error response"""
    error: str
    message: str
    details: Optional[dict] = None

"""
Task Tool
Executes task intent requests (activity-based shopping)
"""
import logging
from typing import List, Dict, Optional
from models.schemas import TaskArguments, TaskResponse, TaskItem, Product
from services.hybrid_search import HybridSearchService
from tools.budget_optimizer import BudgetOptimizer

logger = logging.getLogger(__name__)


# Hardcoded task definitions with validation keywords
TASKS = {
    "Golf": [
        {
            "name": "Golf Clubs",
            "mandatory": True,
            "keywords": ["club", "clubs", "iron", "driver", "putter"],
            "validation_keywords": ["club", "clubs", "iron", "driver", "putter", "wood", "wedge"],
            "negative_keywords": ["brush", "cleaning", "towel", "cover", "sleeve", "holder", "marker", "tee", "repair", "tool", "accessory", "headcover"],
            "sport": "Golf",
            "category": "Golf Equipment"
        },
        {
            "name": "Golf Balls",
            "mandatory": True,
            "keywords": ["ball", "balls"],
            "validation_keywords": ["ball", "balls"],
            "negative_keywords": ["marker", "retriever", "picker", "towel", "brush"],
            "sport": "Golf",
            "category": "Golf Equipment"
        },
        {
            "name": "Golf Bag",
            "mandatory": False,
            "keywords": ["bag", "trolley"],
            "validation_keywords": ["bag", "trolley", "cart", "stand bag", "carry bag"],
            "negative_keywords": ["tee bag", "valuables", "shoe bag", "ball bag", "pouch"],
            "sport": "Golf",
            "category": "Golf Equipment"
        },
        {
            "name": "Golf Gloves",
            "mandatory": False,
            "keywords": ["glove", "gloves"],
            "validation_keywords": ["glove", "gloves"],
            "negative_keywords": [],
            "sport": "Golf",
            "category": "Golf Equipment"
        },
    ],
    "Hiking": [
        {"name": "Hiking Shoes", "mandatory": True, "keywords": ["shoes", "boots"], "validation_keywords": ["shoes", "boots", "footwear"], "negative_keywords": ["brush", "cleaning", "lace", "insole", "cover", "gaiter"], "sport": "Hiking", "category": "Footwear"},
        {"name": "Backpack", "mandatory": True, "keywords": ["backpack", "bag"], "validation_keywords": ["backpack", "pack", "rucksack"], "negative_keywords": ["cover", "rain cover", "pouch", "organizer"], "sport": "Hiking", "category": "Bags"},
        {"name": "Hiking Jacket", "mandatory": False, "keywords": ["jacket"], "validation_keywords": ["jacket", "coat"], "negative_keywords": [], "sport": "Hiking", "category": "Clothing"},
        {"name": "Trekking Poles", "mandatory": False, "keywords": ["pole", "poles", "stick"], "validation_keywords": ["pole", "poles", "stick"], "negative_keywords": ["tip", "rubber", "basket", "cap"], "sport": "Hiking", "category": "Equipment"},
    ],
    "Camping": [
        {"name": "Tent", "mandatory": True, "keywords": ["tent"], "validation_keywords": ["tent"], "negative_keywords": ["peg", "stake", "repair", "groundsheet"], "sport": "Camping", "category": "Camping Equipment"},
        {"name": "Sleeping Bag", "mandatory": True, "keywords": ["sleeping", "bag"], "validation_keywords": ["sleeping", "bag"], "negative_keywords": ["liner", "cover", "compression", "stuff sack"], "sport": "Camping", "category": "Camping Equipment"},
        {"name": "Camping Stove", "mandatory": False, "keywords": ["stove", "cooker"], "validation_keywords": ["stove", "cooker", "burner"], "negative_keywords": ["fuel", "gas", "cartridge", "windshield"], "sport": "Camping", "category": "Camping Equipment"},
        {"name": "Headlamp", "mandatory": False, "keywords": ["headlamp", "light"], "validation_keywords": ["headlamp", "lamp", "light", "torch"], "negative_keywords": ["battery", "bulb", "strap"], "sport": "Camping", "category": "Camping Equipment"},
    ],
    "Running": [
        {"name": "Running Shoes", "mandatory": True, "keywords": ["shoes", "running"], "validation_keywords": ["shoes", "footwear"], "negative_keywords": ["lace", "insole", "brush", "cleaning"], "sport": "Running", "category": "Running Shoes"},
        {"name": "Running Watch", "mandatory": False, "keywords": ["watch", "tracker"], "validation_keywords": ["watch", "tracker"], "negative_keywords": ["strap", "charger", "band"], "sport": "Running", "category": "Electronics"},
        {"name": "Running Shorts", "mandatory": False, "keywords": ["shorts"], "validation_keywords": ["shorts"], "negative_keywords": [], "sport": "Running", "category": "Clothing"},
    ],
    "Football": [
        {"name": "Football Boots", "mandatory": True, "keywords": ["boots", "shoes", "cleats"], "validation_keywords": ["boots", "shoes", "cleats"], "negative_keywords": ["brush", "cleaning", "lace", "insole", "bag"], "sport": "Football", "category": "Football Shoes"},
        {"name": "Football", "mandatory": True, "keywords": ["ball", "football"], "validation_keywords": ["ball", "football"], "negative_keywords": ["pump", "needle", "net", "bag"], "sport": "Football", "category": "Football"},
        {"name": "Shin Guards", "mandatory": False, "keywords": ["shin", "guard"], "validation_keywords": ["shin", "guard"], "negative_keywords": ["sleeve", "sock"], "sport": "Football", "category": "Football Equipment"},
        {"name": "Football Jersey", "mandatory": False, "keywords": ["jersey", "shirt"], "validation_keywords": ["jersey", "shirt"], "negative_keywords": [], "sport": "Football", "category": "Clothing"},
    ],
    "Yoga": [
        {"name": "Yoga Mat", "mandatory": True, "keywords": ["mat", "yoga"], "validation_keywords": ["mat"], "negative_keywords": ["bag", "strap", "towel", "cleaner"], "sport": "Yoga", "category": "Yoga"},
        {"name": "Yoga Block", "mandatory": False, "keywords": ["block"], "validation_keywords": ["block"], "negative_keywords": [], "sport": "Yoga", "category": "Yoga"},
        {"name": "Yoga Strap", "mandatory": False, "keywords": ["strap", "belt"], "validation_keywords": ["strap", "belt"], "negative_keywords": [], "sport": "Yoga", "category": "Yoga"},
    ],
    "Swimming": [
        {"name": "Swimming Goggles", "mandatory": True, "keywords": ["goggles", "glasses"], "validation_keywords": ["goggles", "glasses"], "negative_keywords": ["case", "strap", "anti-fog"], "sport": "Swimming", "category": "Swimming Equipment"},
        {"name": "Swim Cap", "mandatory": False, "keywords": ["cap", "hat"], "validation_keywords": ["cap"], "negative_keywords": [], "sport": "Swimming", "category": "Swimming Equipment"},
        {"name": "Swimsuit", "mandatory": True, "keywords": ["swimsuit", "trunks"], "validation_keywords": ["swimsuit", "trunks", "costume"], "negative_keywords": [], "sport": "Swimming", "category": "Swimwear"},
    ],
    "Cycling": [
        {"name": "Bicycle Helmet", "mandatory": True, "keywords": ["helmet"], "validation_keywords": ["helmet"], "negative_keywords": ["visor", "cover", "light"], "sport": "Cycling", "category": "Cycling Equipment"},
        {"name": "Cycling Gloves", "mandatory": False, "keywords": ["gloves"], "validation_keywords": ["gloves"], "negative_keywords": [], "sport": "Cycling", "category": "Cycling Equipment"},
        {"name": "Water Bottle", "mandatory": False, "keywords": ["bottle", "water"], "validation_keywords": ["bottle"], "negative_keywords": ["cage", "holder", "cap"], "sport": "Cycling", "category": "Accessories"},
    ],
    "Tennis": [
        {"name": "Tennis Racket", "mandatory": True, "keywords": ["racket", "racquet"], "validation_keywords": ["racket", "racquet"], "negative_keywords": ["string", "grip", "overgrip", "bag", "cover"], "sport": "Tennis", "category": "Tennis Equipment"},
        {"name": "Tennis Balls", "mandatory": True, "keywords": ["ball", "balls"], "validation_keywords": ["ball", "balls"], "negative_keywords": ["hopper", "picker", "basket", "tube"], "sport": "Tennis", "category": "Tennis Equipment"},
        {"name": "Tennis Shoes", "mandatory": False, "keywords": ["shoes"], "validation_keywords": ["shoes"], "negative_keywords": ["lace", "insole"], "sport": "Tennis", "category": "Tennis Shoes"},
    ],
    "Basketball": [
        {"name": "Basketball", "mandatory": True, "keywords": ["ball", "basketball"], "validation_keywords": ["ball", "basketball"], "negative_keywords": ["pump", "needle", "net", "bag"], "sport": "Basketball", "category": "Basketball"},
        {"name": "Basketball Shoes", "mandatory": False, "keywords": ["shoes", "sneakers"], "validation_keywords": ["shoes", "sneakers"], "negative_keywords": ["lace", "insole"], "sport": "Basketball", "category": "Basketball Shoes"},
    ],
}


class TaskTool:
    """Tool for executing task intent (activity-based shopping)"""
    
    def __init__(self):
        self.search_service = HybridSearchService()
        self.budget_optimizer = BudgetOptimizer()
    
    def validate_product_for_item(
        self,
        product: Dict,
        validation_keywords: List[str],
        negative_keywords: Optional[List[str]] = None
    ) -> bool:
        """
        Validate if a product matches the expected item type.
        
        Returns True if product name or category contains any validation keyword
        AND does NOT contain any negative keyword.
        This prevents accessories like "Golf Club Cleaning Brush" from being
        selected when searching for "Golf Clubs".
        
        NULL-SAFE: Handles None values in all product fields.
        
        Args:
            product: Product dict with name, categories
            validation_keywords: List of acceptable keywords
            negative_keywords: List of disqualifying keywords (accessories, tools, etc.)
        
        Returns:
            True if product matches expected type, False otherwise
        """
        # NULL-SAFE: Use (product.get('field') or '') to handle None values
        product_name = (product.get('name') or '').lower()
        cat1 = (product.get('category_level_1') or '').lower()
        cat2 = (product.get('category_level_2') or '').lower()
        description = (product.get('description') or '').lower()
        
        # First check negative keywords — reject if any match in name or description
        if negative_keywords:
            for neg_keyword in negative_keywords:
                neg_lower = neg_keyword.lower()
                if neg_lower in product_name or neg_lower in description:
                    return False
        
        # Then check if any validation keyword appears in product name or categories
        for keyword in validation_keywords:
            keyword_lower = keyword.lower()
            if (keyword_lower in product_name or 
                keyword_lower in cat1 or 
                keyword_lower in cat2):
                return True
        
        return False
    
    def execute(self, arguments: TaskArguments) -> TaskResponse:
        """
        Execute task request.
        
        Flow:
            1. Get task definition for activity
            2. Search products for each item
            3. If budget exists, optimize budget
            4. Return grouped results
        
        Args:
            arguments: TaskArguments with activity and optional budget
        
        Returns:
            TaskResponse with items and products
        """
        activity = arguments.activity
        budget = arguments.budget
        
        logger.info(f"Executing task: activity={activity}, budget={budget}")
        
        # Get task definition
        if activity not in TASKS:
            logger.error(f"Unknown activity: {activity}")
            raise ValueError(f"Activity '{activity}' not supported. Supported: {list(TASKS.keys())}")
        
        task_definition = TASKS[activity]
        
        # Search products for each item
        items = []
        all_products = {}
        
        for item_def in task_definition:
            item_name = item_def["name"]
            mandatory = item_def["mandatory"]
            keywords = item_def["keywords"]
            validation_keywords = item_def.get("validation_keywords", keywords)
            negative_keywords = item_def.get("negative_keywords", [])
            sport = item_def.get("sport", activity)
            category = item_def.get("category")
            
            logger.info(f"Searching for: {item_name} (mandatory={mandatory})")
            logger.info(f"  Keywords: {keywords}")
            logger.info(f"  Validation: {validation_keywords}")
            logger.info(f"  Negative: {negative_keywords}")
            
            # Search products — get top 10 for a richer discovery list
            products = self.search_service.search(
                sport=sport,
                category_level_1=category,
                keywords=keywords,
                price_limit=budget,  # Pre-filter by budget if set
                top_k=10
            )
            
            # Validate products - filter out mismatches
            validated_products = []
            rejected_products = []
            
            for product in products:
                is_valid = self.validate_product_for_item(product, validation_keywords, negative_keywords)
                
                if is_valid:
                    validated_products.append(product)
                else:
                    rejected_products.append(product)
                    logger.warning(f"  ❌ REJECTED: {product['name']} (doesn't match {validation_keywords})")
            
            if rejected_products:
                logger.info(f"  ✓ Validated: {len(validated_products)}/{len(products)} products")
            
            # Convert to Product objects (all validated, up to 8 for discovery)
            product_objects = [Product(**p) for p in validated_products[:8]]
            
            if not product_objects and mandatory:
                logger.warning(f"  ⚠️  No valid products found for mandatory item: {item_name}")
            
            # Store for budget optimization
            all_products[item_name] = product_objects
            
            # Create TaskItem
            task_item = TaskItem(
                name=item_name,
                mandatory=mandatory,
                products=product_objects
            )
            items.append(task_item)
        
        # If budget exists, optimize
        total_cost = None
        within_budget = None
        budget_remaining = None

        if budget:
            logger.info(f"Optimizing budget: ₹{budget}")
            optimized = self.budget_optimizer.optimize(
                items=items,
                budget=budget
            )

            if not optimized.get("success", True):
                logger.error(f"Budget optimization failed: {optimized.get('message')}")
                # Still return items in discovery mode even if budget fails
            
            items            = optimized["items"]
            total_cost       = optimized.get("total_cost")
            within_budget    = optimized.get("within_budget")
            budget_remaining = optimized.get("budget_remaining")
        else:
            # No budget — rank products and set recommended for each item
            items = self.budget_optimizer.discover(items)
            total_cost = sum(
                item.budget_allocated for item in items
                if item.budget_allocated and item.recommended
            )
        
        response = TaskResponse(
            activity=activity,
            budget=budget,
            budget_remaining=budget_remaining,
            total_cost=total_cost or None,
            within_budget=within_budget,
            items=items,
        )
        
        logger.info(f"Task returned {len(items)} items")
        
        return response

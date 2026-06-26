"""
Task Tool
Executes task intent requests (activity-based shopping)
"""
import logging
import re
from typing import List, Dict, Optional
from models.schemas import TaskArguments, TaskResponse, TaskItem, Product
from services.hybrid_search import HybridSearchService
from tools.budget_optimizer import BudgetOptimizer

logger = logging.getLogger(__name__)


KIDS_QUERY_SIGNALS = ["kid", "kids", "child", "children", "son", "daughter", "boy", "boys", "girl", "girls", "junior"]
BEGINNER_QUERY_SIGNALS = ["start", "begin", "beginner", "new to", "first time", "learn", "getting into", "try"]
BUDGET_QUERY_SIGNALS = ["cheap", "budget", "affordable", "under", "low cost", "economical", "inexpensive", "value"]
PREMIUM_QUERY_SIGNALS = ["best", "high-end", "premium", "professional", "advanced", "pro", "elite", "top"]

KIDS_KEYWORDS = {"kids", "kid", "junior", "children", "child", "youth", "boy", "boys", "girl", "girls", "toddler", "toddlers"}


def is_kids_product(product: Product) -> bool:
    text = f"{product.name or ''} {product.description or ''} {product.category_level_1 or ''} {product.category_level_2 or ''}".lower()
    words = re.findall(r'\b\w+\b', text)
    return any(w in KIDS_KEYWORDS for w in words)


def infer_user_profile(query: str) -> Dict[str, bool]:
    q = (query or "").lower()
    return {
        "is_kids": any(signal in q for signal in KIDS_QUERY_SIGNALS),
        "is_beginner": any(signal in q for signal in BEGINNER_QUERY_SIGNALS),
        "budget_sensitive": any(signal in q for signal in BUDGET_QUERY_SIGNALS),
        "premium_intent": any(signal in q for signal in PREMIUM_QUERY_SIGNALS),
    }


def compute_profile_score(product: Product, user_profile: Dict[str, bool]) -> float:
    # Start with a base profile score of 1.0 (perfect match / neutral)
    score = 1.0
    
    # 1. Kids check
    is_kids = is_kids_product(product)
    if user_profile["is_kids"]:
        if not is_kids:
            # User wants a kids product, but this is an adult product (mild mismatch)
            score = min(score, 0.3)
    else:
        if is_kids:
            # User wants an adult product, but this is a kids product (severe mismatch)
            score = min(score, 0.1)
            
    # 2. Experience level check
    product_name = (product.name or "").lower()
    product_desc = (product.description or "").lower()
    product_text = f"{product_name} {product_desc}"
    
    is_beginner_prod = any(kw in product_text for kw in ["beginner", "beginners", "start", "starting", "easy", "learn", "introduction", "first", "entry-level", "entry level", "basic"])
    is_advanced_prod = any(kw in product_text for kw in ["advanced", "expert", "professional", "pro", "competition", "technical", "performance", "intensive"])
    
    if user_profile["is_beginner"]:
        if is_advanced_prod and not is_beginner_prod:
            score = min(score, 0.7)
    elif user_profile["premium_intent"]:
        if is_beginner_prod and not is_advanced_prod:
            score = min(score, 0.7)
            
    return score


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
        
        # First check negative keywords — reject if any match as a full word/phrase in name or description
        if negative_keywords:
            text_to_check = f"{product_name} {description}".lower()
            product_words = set(re.findall(r'\b\w+\b', text_to_check))
            for neg_keyword in negative_keywords:
                neg_lower = neg_keyword.lower()
                # If negative keyword has spaces, check substring with word boundaries
                if " " in neg_lower:
                    if re.search(r'\b' + re.escape(neg_lower) + r'\b', text_to_check):
                        return False
                else:
                    if neg_lower in product_words:
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
        
        logger.info("=" * 80)
        logger.info(f"TASKTOOL EXECUTION START")
        logger.info(f"Activity: {activity}, Budget: {budget}")
        logger.info("=" * 80)
        
        # Get task definition
        if activity not in TASKS:
            logger.error(f"Unknown activity: {activity}")
            raise ValueError(f"Activity '{activity}' not supported. Supported: {list(TASKS.keys())}")
        
        task_definition = TASKS[activity]
        
        # Infer user profile once for the entire task
        user_profile = infer_user_profile(arguments.query or "")
        
        # Search products for each item
        items = []
        all_products = {}
        
        logger.info(f"Searching for {len(task_definition)} items:")
        for idx, item_def in enumerate(task_definition, 1):
            logger.info(f"  {idx}. {item_def['name']}")
        
        for item_index, item_def in enumerate(task_definition, 1):
            item_name = item_def["name"]
            mandatory = item_def["mandatory"]
            keywords = item_def["keywords"]
            validation_keywords = item_def.get("validation_keywords", keywords)
            negative_keywords = item_def.get("negative_keywords", [])
            sport = item_def.get("sport", activity)
            category = item_def.get("category")
            
            logger.info("-" * 80)
            logger.info(f"ITEM {item_index}/{len(task_definition)}: {item_name}")
            logger.info(f"  Mandatory: {mandatory}")
            logger.info(f"  Keywords: {keywords}")
            logger.info(f"  Validation: {validation_keywords}")
            logger.info(f"  Negative: {negative_keywords}")
            logger.info("-" * 80)
            
            # Search products — get top 20 for a richer candidate pool
            # Profile scoring needs enough candidates to re-rank (e.g., kids products
            # often rank lower in generic search but should surface for kids queries)
            products = self.search_service.search(
                sport=sport,
                category_level_1=category,
                keywords=keywords,
                price_limit=budget,  # Pre-filter by budget if set
                top_k=20,
                return_format='flat'  # Backward compatibility: get flat list of RELEVANT products only
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
            
            # Convert to Product objects (all validated, up to 20 for discovery/ranking)
            product_objects = []
            for p in validated_products:
                p_dict = dict(p)
                if "similarity" not in p_dict and "final_score" in p_dict:
                    p_dict["similarity"] = p_dict["final_score"]
                prod = Product(**p_dict)
                prod.profile_score = compute_profile_score(prod, user_profile)
                product_objects.append(prod)
            
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
            
            logger.info(f"✓ Item '{item_name}' search complete")
        
        logger.info("=" * 80)
        logger.info("ALL ITEM SEARCHES COMPLETE")
        logger.info("=" * 80)
        
        # If budget exists, optimize
        total_cost = None
        within_budget = None
        budget_remaining = None

        if budget:
            logger.info(f"Optimizing budget: ₹{budget}")
            optimized = self.budget_optimizer.optimize(
                items=items,
                budget=budget,
                user_profile=user_profile
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
            items = self.budget_optimizer.discover(items, user_profile=user_profile)
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
            query=arguments.query,
        )
        
        logger.info("=" * 80)
        logger.info(f"TASKTOOL EXECUTION COMPLETE")
        logger.info(f"Returned {len(items)} items")
        logger.info("=" * 80)
        
        return response

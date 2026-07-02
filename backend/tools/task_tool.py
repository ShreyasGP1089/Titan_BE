"""
Task Tool
Executes task intent requests (activity-based shopping)
"""
import logging
import re
import time
from typing import List, Dict, Optional
from models.schemas import TaskArguments, TaskResponse, TaskItem, Product
from services.hybrid_search import HybridSearchService
from services.planner_service import PlannerService
from services.search_query_parser_service import SearchQueryParserService
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
        self.planner_service = PlannerService()
        self.search_query_parser = SearchQueryParserService()
        self.budget_optimizer = BudgetOptimizer()
    
    def _parse_product_to_search_request(self, product_name: str, sport: str) -> Dict:
        """
        Parse a product name into an optimal search request using Search Query Parser.
        
        This replaces the old _create_search_request_from_product_name() method
        with an SLM-based parser that determines optimal categories and keywords.
        
        Args:
            product_name: Product name from planner (e.g., "Golf Shirt")
            sport: Sport name for context
        
        Returns:
            Dict with sport, category_level_1, category_level_2, keywords
        
        Examples:
            "Golf Shirt" → {"sport": "Golf", "category_level_1": "Apparel", "keywords": ["golf shirt"]}
            "Running Shoes" → {"sport": "Running", "category_level_1": "Footwear", "keywords": ["running shoes"]}
        """
        return self.search_query_parser.parse_search_query(product_name, sport)
    
    def _get_planned_products(
        self,
        activity: str,
        sport: str,
        user_query: Optional[str] = None,
        parser_items: Optional[List] = None
    ) -> tuple[List[Dict], str]:
        """
        Get planned products from multiple sources (priority order):
        1. Parser items (if provided)
        2. Dynamic planner
        3. Fallback to TASKS dictionary
        
        Args:
            activity: Activity name
            sport: Sport name
            user_query: Optional user query for context
            parser_items: Optional pre-planned items from parser
        
        Returns:
            Tuple of (planned_products_list, source)
            where source is "parser", "dynamic", or "fallback"
            
            planned_products_list format:
            [
                {"name": "Golf Shirt", "mandatory": True},
                {"name": "Golf Shorts", "mandatory": True},
                ...
            ]
        """
        logger.info("=" * 80)
        logger.info("PLANNED PRODUCTS RESOLUTION")
        logger.info("=" * 80)
        
        # PRIORITY 1: Use parser items if provided
        if parser_items:
            logger.info(f"✓ Using PARSER items ({len(parser_items)} items provided)")
            logger.info("=" * 80)
            logger.info("PARSER ITEMS (RAW):")
            for idx, item in enumerate(parser_items, 1):
                logger.info(f"  {idx}. {item.name} ({'mandatory' if item.mandatory else 'optional'})")
            logger.info("=" * 80)
            
            # Convert parser items to simple format
            planned_products = [
                {"name": item.name, "mandatory": item.mandatory}
                for item in parser_items
            ]
            
            # DEDUPLICATION: Remove duplicate items, keeping first occurrence
            # Use case-insensitive comparison for product names
            seen_names = set()
            deduplicated_products = []
            duplicates_removed = []
            
            for product in planned_products:
                name_lower = product["name"].lower().strip()
                if name_lower not in seen_names:
                    seen_names.add(name_lower)
                    deduplicated_products.append(product)
                else:
                    duplicates_removed.append(product["name"])
            
            if duplicates_removed:
                logger.info("=" * 80)
                logger.info("⚠️  DUPLICATES DETECTED AND REMOVED:")
                logger.info(f"   Original count: {len(planned_products)}")
                logger.info(f"   After deduplication: {len(deduplicated_products)}")
                logger.info(f"   Removed: {duplicates_removed}")
                logger.info("=" * 80)
            
            planned_products = deduplicated_products
            
            # BOUNDARY 4: OUT OF _get_planned_products() (parser path)
            logger.info("=" * 80)
            logger.info("[OUTPUT FROM _get_planned_products()]")
            logger.info("=" * 80)
            logger.info("Source: parser")
            logger.info("Items (after deduplication):")
            for idx, product in enumerate(planned_products, 1):
                mandatory_str = "mandatory" if product["mandatory"] else "optional"
                logger.info(f"  {idx}. {product['name']} ({mandatory_str})")
            logger.info("=" * 80)
            
            return planned_products, "parser"
        
        # PRIORITY 2: Try dynamic planner
        logger.info(f"No parser items provided. Attempting dynamic planner for: {activity}")
        logger.info("=" * 80)
        
        planner_result = self.planner_service.plan_task(
            activity=activity,
            sport=sport,
            user_query=user_query
        )
        
        # BOUNDARY 1: PLANNER OUTPUT
        logger.info("=" * 80)
        logger.info("[PLANNER OUTPUT]")
        logger.info("=" * 80)
        if planner_result and planner_result.get("items"):
            logger.info("Items returned:")
            for idx, item in enumerate(planner_result["items"], 1):
                mandatory_str = "mandatory" if item.get("mandatory", True) else "optional"
                logger.info(f"  {idx}. {item.get('name')} ({mandatory_str})")
            logger.info(f"Confidence: {planner_result.get('confidence', 0.0):.2f}")
        else:
            logger.info("No items returned")
        logger.info("=" * 80)
        
        if planner_result and planner_result.get("items"):
            # Check confidence threshold
            confidence = planner_result.get("confidence", 0.0)
            
            # BOUNDARY 3: INSIDE _get_planned_products() - DECISION POINT
            logger.info("=" * 80)
            logger.info("[_get_planned_products() DECISION]")
            logger.info("=" * 80)
            logger.info("Planner returned:")
            for idx, item in enumerate(planner_result["items"], 1):
                mandatory_str = "mandatory" if item.get("mandatory", True) else "optional"
                logger.info(f"  {idx}. {item.get('name')} ({mandatory_str})")
            logger.info(f"Confidence: {confidence:.2f}")
            logger.info(f"Threshold: 0.5")
            
            if confidence >= 0.5:  # Confidence threshold
                logger.info("Decision: ✓ ACCEPT (confidence >= threshold)")
                logger.info("=" * 80)
                logger.info(f"✓ Using DYNAMIC planner (confidence: {confidence:.2f})")
                
                # Convert planner items to simple planned products format
                planned_products = [
                    {
                        "name": item.get("name"),
                        "mandatory": item.get("mandatory", True)
                    }
                    for item in planner_result["items"]
                ]
                
                # DEDUPLICATION: Remove duplicate items
                seen_names = set()
                deduplicated_products = []
                duplicates_removed = []
                
                for product in planned_products:
                    name_lower = product["name"].lower().strip()
                    if name_lower not in seen_names:
                        seen_names.add(name_lower)
                        deduplicated_products.append(product)
                    else:
                        duplicates_removed.append(product["name"])
                
                if duplicates_removed:
                    logger.info("=" * 80)
                    logger.info("⚠️  DUPLICATES DETECTED AND REMOVED:")
                    logger.info(f"   Original count: {len(planned_products)}")
                    logger.info(f"   After deduplication: {len(deduplicated_products)}")
                    logger.info(f"   Removed: {duplicates_removed}")
                    logger.info("=" * 80)
                
                planned_products = deduplicated_products
                
                logger.info("=" * 80)
                logger.info("PLANNED PRODUCTS FROM PLANNER (AFTER DEDUPLICATION)")
                for idx, product in enumerate(planned_products, 1):
                    logger.info(f"  {idx}. {product['name']} ({'mandatory' if product['mandatory'] else 'optional'})")
                logger.info("=" * 80)
                
                # BOUNDARY 4: OUT OF _get_planned_products()
                logger.info("=" * 80)
                logger.info("[OUTPUT FROM _get_planned_products()]")
                logger.info("=" * 80)
                logger.info("Source: dynamic")
                logger.info("Items:")
                for idx, product in enumerate(planned_products, 1):
                    mandatory_str = "mandatory" if product["mandatory"] else "optional"
                    logger.info(f"  {idx}. {product['name']} ({mandatory_str})")
                logger.info("=" * 80)
                
                return planned_products, "dynamic"
            else:
                logger.info("Decision: ✗ REJECT (confidence < threshold)")
                logger.info("Triggering fallback to TASKS")
                logger.info("=" * 80)
                logger.warning(f"⚠️  Planner confidence too low: {confidence:.2f} (threshold: 0.5)")
        else:
            logger.warning("⚠️  Dynamic planner failed or returned no items")
        
        # PRIORITY 3: Fallback to hardcoded TASKS
        if activity in TASKS:
            logger.info(f"→ Falling back to HARDCODED task definition")
            
            # Convert TASKS format to simple planned products format
            planned_products = [
                {
                    "name": item["name"],
                    "mandatory": item["mandatory"]
                }
                for item in TASKS[activity]
            ]
            
            # DEDUPLICATION: Remove duplicate items (safety check for hardcoded tasks)
            seen_names = set()
            deduplicated_products = []
            duplicates_removed = []
            
            for product in planned_products:
                name_lower = product["name"].lower().strip()
                if name_lower not in seen_names:
                    seen_names.add(name_lower)
                    deduplicated_products.append(product)
                else:
                    duplicates_removed.append(product["name"])
            
            if duplicates_removed:
                logger.warning("=" * 80)
                logger.warning("⚠️  DUPLICATES FOUND IN HARDCODED TASKS (FIX NEEDED):")
                logger.warning(f"   Original count: {len(planned_products)}")
                logger.warning(f"   After deduplication: {len(deduplicated_products)}")
                logger.warning(f"   Removed: {duplicates_removed}")
                logger.warning("=" * 80)
            
            planned_products = deduplicated_products
            
            # BOUNDARY 4: OUT OF _get_planned_products() (fallback path)
            logger.info("=" * 80)
            logger.info("[OUTPUT FROM _get_planned_products()]")
            logger.info("=" * 80)
            logger.info("Source: fallback")
            logger.info("Items:")
            for idx, product in enumerate(planned_products, 1):
                mandatory_str = "mandatory" if product["mandatory"] else "optional"
                logger.info(f"  {idx}. {product['name']} ({mandatory_str})")
            logger.info("=" * 80)
            
            return planned_products, "fallback"
        else:
            logger.error(f"❌ No task definition found for: {activity}")
            raise ValueError(f"Activity '{activity}' not supported. Supported: {list(TASKS.keys())}")
    
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
        Execute task request using product-centric architecture.
        
        Flow:
            1. Get planned products (from parser, planner, or fallback)
            2. FOR EACH planned product:
               - Create search request
               - Call Hybrid Search (handles retrieval + validation)
               - Collect results
            3. Budget optimization
            4. Return bundle
        
        Each planned product is treated as an independent search,
        exactly as if the user searched for that product individually.
        
        Args:
            arguments: TaskArguments with activity and optional budget
        
        Returns:
            TaskResponse with items and products
        """
        # ================================================================
        # PERFORMANCE PROFILING START
        # ================================================================
        t_task_start = time.time()
        t_parsing_start = time.time()
        
        activity = arguments.activity
        budget = arguments.budget
        user_query = arguments.query
        parser_items = arguments.items
        
        logger.info("=" * 80)
        logger.info("STAGE 3: TaskTool.execute() RECEIVED TaskArguments")
        logger.info("=" * 80)
        logger.info(f"Activity: {activity}")
        logger.info(f"Budget: {budget}")
        logger.info(f"User Query: {user_query}")
        if parser_items:
            logger.info(f"Parser Items RECEIVED: {len(parser_items)} items")
            for idx, item in enumerate(parser_items, 1):
                logger.info(f"  {idx}. {item.name} ({'mandatory' if item.mandatory else 'optional'})")
        else:
            logger.info(f"Parser Items RECEIVED: None")
        logger.info("=" * 80)
        
        logger.info("=" * 80)
        logger.info(f"TASK PERFORMANCE PROFILE")
        logger.info(f"Activity: {activity}, Budget: {budget}")
        logger.info(f"User Query: {user_query}")
        logger.info(f"Parser Items: {len(parser_items) if parser_items else 0}")
        logger.info("=" * 80)
        
        # Get planned products (simple list of product names + mandatory flag)
        sport = activity  # Extract sport from activity
        
        planned_products, definition_source = self._get_planned_products(
            activity=activity,
            sport=sport,
            user_query=user_query,
            parser_items=parser_items
        )
        
        logger.info("=" * 80)
        logger.info("STAGE 4: AFTER _get_planned_products()")
        logger.info("=" * 80)
        logger.info(f"Product source: {definition_source}")
        logger.info(f"Products to search: {len(planned_products)}")
        logger.info("PLANNED PRODUCTS LIST:")
        for idx, product in enumerate(planned_products, 1):
            mandatory_str = "mandatory" if product["mandatory"] else "optional"
            logger.info(f"  {idx}. {product['name']} ({mandatory_str})")
        logger.info("=" * 80)
        logger.info("")
        
        # Infer user profile once for the entire task
        user_profile = infer_user_profile(user_query or "")
        
        t_parsing_end = time.time()
        t_parsing_duration = (t_parsing_end - t_parsing_start) * 1000
        
        logger.info(f"Task Parsing & Planning")
        logger.info(f"  Duration: {t_parsing_duration:.1f} ms")
        logger.info(f"  Source: {definition_source.upper()}")
        logger.info("-" * 80)
        
        # Performance tracking
        perf_items = []
        total_search_time = 0
        total_products_retrieved = 0
        
        # Search products for each planned product
        items = []
        all_products = {}
        
        # BOUNDARY 5: ENTERING SEARCH LOOP
        logger.info("=" * 80)
        logger.info("[SEARCH LOOP START]")
        logger.info("=" * 80)
        logger.info(f"Items to search: {len(planned_products)}")
        logger.info("Loop will search:")
        for idx, planned_product in enumerate(planned_products, 1):
            mandatory_str = "mandatory" if planned_product["mandatory"] else "optional"
            logger.info(f"  {idx}. {planned_product['name']} ({mandatory_str})")
        logger.info("=" * 80)
        logger.info("")
        
        for item_index, planned_product in enumerate(planned_products, 1):
            product_name = planned_product["name"]
            mandatory = planned_product["mandatory"]
            
            # BOUNDARY 6: FOR EACH ITEM - EXTRACTION
            logger.info("=" * 80)
            logger.info(f"[SEARCH LOOP ITERATION {item_index}/{len(planned_products)}]")
            logger.info("=" * 80)
            logger.info("Extracted from planned_products:")
            logger.info(f"  product_name: \"{product_name}\"")
            logger.info(f"  mandatory: {mandatory}")
            logger.info("=" * 80)
            logger.info("")
            
            logger.info("=" * 80)
            logger.info(f"PRODUCT {item_index}/{len(planned_products)}: {product_name}")
            logger.info("=" * 80)
            
            # BOUNDARY 7: INTO parse-search-query
            logger.info("=" * 80)
            logger.info("[INPUT TO parse-search-query]")
            logger.info("=" * 80)
            logger.info(f"Product name: \"{product_name}\"")
            logger.info(f"Sport: \"{sport}\"")
            logger.info("=" * 80)
            
            # Parse product name into optimal search request using Search Query Parser
            search_request = self._parse_product_to_search_request(product_name, sport)
            
            # BOUNDARY 8: OUT OF parse-search-query
            logger.info("=" * 80)
            logger.info("[OUTPUT FROM parse-search-query]")
            logger.info("=" * 80)
            logger.info(f"Input was: \"{product_name}\"")
            logger.info("Output:")
            logger.info(f"  sport: {search_request['sport']}")
            logger.info(f"  category_level_1: {search_request.get('category_level_1')}")
            logger.info(f"  keywords: {search_request['keywords']}")
            logger.info("=" * 80)
            
            logger.info("=" * 80)
            logger.info("HYBRID SEARCH REQUEST")
            logger.info(f"  Planner Item: {product_name}")
            logger.info(f"  Search Parameters:")
            logger.info(f"    sport: {search_request['sport']}")
            logger.info(f"    category: {search_request.get('category_level_1')}")
            logger.info(f"    keywords: {search_request['keywords']}")
            logger.info("=" * 80)
            
            # BOUNDARY 9: INTO HYBRID SEARCH
            logger.info("=" * 80)
            logger.info("[INPUT TO HYBRID SEARCH]")
            logger.info("=" * 80)
            logger.info(f"For planner item: \"{product_name}\"")
            logger.info("Arguments:")
            logger.info(f"  sport: {search_request['sport']}")
            logger.info(f"  category_level_1: {search_request.get('category_level_1')}")
            logger.info(f"  keywords: {search_request['keywords']}")
            logger.info(f"  price_limit: {budget}")
            logger.info(f"  top_k: 20")
            logger.info("=" * 80)
            
            # ADDITIONAL GRANULAR LOGGING: Verify variables before search
            logger.info("=" * 80)
            logger.info("SEARCH LOOP - IMMEDIATE PRE-SEARCH CHECK")
            logger.info(f"Current planned_product dict: {planned_product}")
            logger.info(f"Product name variable: \"{product_name}\"")
            logger.info(f"Mandatory variable: {mandatory}")
            logger.info("=" * 80)
            
            t_item_search_start = time.time()
            
            # Call Hybrid Search - it handles retrieval + validation
            search_result = self.search_service.search(
                sport=search_request["sport"],
                category_level_1=search_request.get("category_level_1"),
                keywords=search_request["keywords"],
                price_limit=budget,
                top_k=20,
                return_format='dict'  # Get both RELEVANT and RELATED
            )
            
            t_item_search_end = time.time()
            t_item_search_duration = (t_item_search_end - t_item_search_start) * 1000
            total_search_time += t_item_search_duration
            
            # Extract RELEVANT products (Hybrid Search already validated)
            relevant_products = search_result.get('relevant', [])
            related_products = search_result.get('related', [])
            
            # BOUNDARY 10: OUT OF HYBRID SEARCH
            logger.info("=" * 80)
            logger.info("[OUTPUT FROM HYBRID SEARCH]")
            logger.info("=" * 80)
            logger.info(f"For planner item: \"{product_name}\"")
            logger.info(f"RELEVANT: {len(relevant_products)} products")
            if relevant_products:
                logger.info("Top products:")
                for p in relevant_products[:5]:
                    logger.info(f"  - {p['name']} (₹{p['price']})")
                if len(relevant_products) > 5:
                    logger.info(f"  ... and {len(relevant_products) - 5} more")
            logger.info(f"RELATED: {len(related_products)} products")
            logger.info("=" * 80)
            
            candidates_retrieved = len(relevant_products)
            candidates_sent_to_validator = min(candidates_retrieved, 25)  # Hybrid Search validates top 25
            total_products_retrieved += len(relevant_products)
            
            logger.info("=" * 80)
            logger.info("RETRIEVAL & VALIDATION COMPLETE")
            logger.info(f"  Planner Item: {product_name}")
            logger.info(f"  Duration: {t_item_search_duration:.1f} ms")
            logger.info(f"  Candidates Retrieved: {candidates_retrieved + len(related_products)}")
            logger.info(f"  Candidates Sent To Validator: {candidates_sent_to_validator}")
            logger.info(f"  RELEVANT products: {len(relevant_products)}")
            logger.info(f"  RELATED products: {len(related_products)}")
            logger.info("=" * 80)
            
            # Convert to Product objects
            product_objects = []
            for p in relevant_products:
                p_dict = dict(p)
                if "similarity" not in p_dict and "final_score" in p_dict:
                    p_dict["similarity"] = p_dict["final_score"]
                prod = Product(**p_dict)
                prod.profile_score = compute_profile_score(prod, user_profile)
                product_objects.append(prod)
            
            if not product_objects and mandatory:
                logger.warning(f"  ⚠️  No valid products found for mandatory product: {product_name}")
            
            # Store for budget optimization
            all_products[product_name] = product_objects
            
            # Create TaskItem
            task_item = TaskItem(
                name=product_name,
                mandatory=mandatory,
                products=product_objects
            )
            items.append(task_item)
            
            # Track item performance
            perf_items.append({
                "name": product_name,
                "search_ms": t_item_search_duration,
                "retrieved": len(relevant_products)
            })
            
            logger.info(f"✓ Product '{product_name}' search complete")
            logger.info("")
        
        logger.info("=" * 80)
        logger.info("ALL PRODUCT SEARCHES COMPLETE")
        logger.info("=" * 80)
        logger.info("")
        
        # Budget optimization
        t_budget_start = time.time()
        
        total_cost = None
        within_budget = None
        budget_remaining = None
        minimum_budget_required = None
        error_message = None

        # ================================================================
        # DIAGNOSTIC: BUDGET OPTIMIZER ENTRY POINT
        # ================================================================
        logger.info("=" * 80)
        logger.info("[BUDGET OPTIMIZER - ENTRY POINT]")
        logger.info("=" * 80)
        logger.info(f"Budget received: ₹{budget}")
        logger.info(f"Items before optimizer: {len(items)}")
        for idx, item in enumerate(items, 1):
            product_count = len(item.products) if item.products else 0
            cheapest = min(item.products, key=lambda p: p.price) if item.products else None
            if cheapest:
                logger.info(f"  {idx}. {item.name} ({product_count} products)")
                logger.info(f"      Cheapest: ₹{cheapest.price:.2f} - {cheapest.name}")
                logger.info(f"      Current recommended: {item.recommended.name if item.recommended else 'None'}")
                logger.info(f"      Current budget_allocated: {item.budget_allocated}")
            else:
                logger.info(f"  {idx}. {item.name} (0 products)")
        logger.info("=" * 80)
        logger.info("")

        if budget:
            logger.info(f"Budget Optimization")
            logger.info(f"  Start: {t_budget_start:.3f}")
            logger.info(f"  Budget: ₹{budget}")
            
            logger.info("=" * 80)
            logger.info("[CALLING BUDGET_OPTIMIZER.OPTIMIZE()]")
            logger.info("=" * 80)
            
            optimized = self.budget_optimizer.optimize(
                items=items,
                budget=budget,
                user_profile=user_profile
            )

            logger.info("=" * 80)
            logger.info("[BUDGET_OPTIMIZER.OPTIMIZE() RETURNED]")
            logger.info("=" * 80)
            logger.info(f"Success: {optimized.get('success')}")
            logger.info(f"Message: {optimized.get('message')}")
            logger.info(f"Total cost: {optimized.get('total_cost')}")
            logger.info(f"Within budget: {optimized.get('within_budget')}")
            logger.info(f"Budget remaining: {optimized.get('budget_remaining')}")
            logger.info(f"Minimum budget required: {optimized.get('minimum_budget_required')}")
            logger.info(f"Items returned: {len(optimized.get('items', []))}")
            logger.info("=" * 80)
            logger.info("")

            if not optimized.get("success", True):
                logger.error(f"Budget optimization failed: {optimized.get('message')}")
                error_message = optimized.get('message')
            
            items                    = optimized["items"]
            total_cost               = optimized.get("total_cost")
            within_budget            = optimized.get("within_budget")
            budget_remaining         = optimized.get("budget_remaining")
            minimum_budget_required  = optimized.get("minimum_budget_required")
            
            # ================================================================
            # DIAGNOSTIC: AFTER OPTIMIZER
            # ================================================================
            logger.info("=" * 80)
            logger.info("[AFTER BUDGET OPTIMIZER]")
            logger.info("=" * 80)
            logger.info(f"Variables captured:")
            logger.info(f"  total_cost: {total_cost}")
            logger.info(f"  within_budget: {within_budget}")
            logger.info(f"  budget_remaining: {budget_remaining}")
            logger.info(f"  minimum_budget_required: {minimum_budget_required}")
            logger.info(f"  error_message: {error_message}")
            logger.info("")
            logger.info("Items after optimizer:")
            running_total = 0.0
            for idx, item in enumerate(items, 1):
                logger.info(f"  {idx}. {item.name}")
                if item.recommended:
                    logger.info(f"      Recommended: {item.recommended.name}")
                    logger.info(f"      Price: ₹{item.recommended.price:.2f}")
                    logger.info(f"      budget_allocated: {item.budget_allocated}")
                    if item.budget_allocated:
                        running_total += item.budget_allocated
                        logger.info(f"      Running total: ₹{running_total:.2f}")
                else:
                    logger.info(f"      Recommended: None")
                    logger.info(f"      budget_allocated: {item.budget_allocated}")
            logger.info("")
            logger.info(f"Manual running total: ₹{running_total:.2f}")
            if budget:
                logger.info(f"Manual remaining: ₹{(budget - running_total):.2f}")
            if minimum_budget_required:
                logger.info(f"Minimum budget required: ₹{minimum_budget_required:.2f}")
            logger.info("=" * 80)
            logger.info("")
        else:
            logger.info(f"No Budget - Discovery Mode")
            logger.info(f"  Start: {t_budget_start:.3f}")
            
            items = self.budget_optimizer.discover(items, user_profile=user_profile)
            total_cost = sum(
                item.budget_allocated for item in items
                if item.budget_allocated and item.recommended
            )
        
        t_budget_end = time.time()
        t_budget_duration = (t_budget_end - t_budget_start) * 1000
        
        logger.info(f"  End: {t_budget_end:.3f}")
        logger.info(f"  Duration: {t_budget_duration:.1f} ms")
        logger.info("")
        
        # Log final bundle before response formatting
        # BOUNDARY 11: FINAL BUNDLE
        logger.info("=" * 80)
        logger.info("[FINAL BUNDLE]")
        logger.info("=" * 80)
        logger.info("Items in bundle:")
        for idx, item in enumerate(items, 1):
            if item.recommended:
                logger.info(f"  {idx}. {item.name}")
                logger.info(f"     Selected: {item.recommended.name} (₹{item.recommended.price})")
            else:
                logger.info(f"  {idx}. {item.name}")
                logger.info(f"     Selected: None (no products found)")
        if total_cost:
            logger.info(f"Total: ₹{total_cost}")
        logger.info("=" * 80)
        
        logger.info("=" * 80)
        logger.info("FINAL TASK RESULT")
        logger.info("=" * 80)
        for idx, item in enumerate(items, 1):
            if item.recommended:
                logger.info(f"  Planner Item: {item.name}")
                logger.info(f"    Selected: {item.recommended.name}")
                logger.info(f"    Price: ₹{item.recommended.price}")
            else:
                logger.info(f"  Planner Item: {item.name}")
                logger.info(f"    Selected: None (no products found)")
        
        if total_cost:
            logger.info(f"  Estimated Total: ₹{total_cost:,.0f}")
        if budget:
            logger.info(f"  Budget: ₹{budget:,.0f}")
            if within_budget is not None:
                status = "✓ Within Budget" if within_budget else "✗ Over Budget"
                logger.info(f"  Status: {status}")
            if budget_remaining is not None:
                logger.info(f"  Remaining: ₹{budget_remaining:,.0f}")
        logger.info("=" * 80)
        logger.info("")
        
        # Response formatting
        t_formatting_start = time.time()
        
        # Build user-friendly error message if budget insufficient
        user_message = None
        if minimum_budget_required and budget:
            user_message = f"Sorry, the minimum budget required is ₹{minimum_budget_required:,.0f}. Your budget of ₹{budget:,.0f} is insufficient to cover all mandatory items."
        
        response = TaskResponse(
            activity=activity,
            budget=budget,
            budget_remaining=budget_remaining,
            total_cost=total_cost or None,
            within_budget=within_budget,
            minimum_budget_required=minimum_budget_required,
            message=user_message,
            items=items,
            query=arguments.query,
        )
        
        t_formatting_end = time.time()
        t_formatting_duration = (t_formatting_end - t_formatting_start) * 1000
        
        t_task_end = time.time()
        t_task_total = (t_task_end - t_task_start) * 1000
        
        # ================================================================
        # PERFORMANCE SUMMARY
        # ================================================================
        logger.info("=" * 80)
        logger.info("PERFORMANCE SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Task Parsing & Planning: {t_parsing_duration:.1f} ms")
        logger.info(f"Product Search (Hybrid Search + Validation): {total_search_time:.1f} ms ({total_search_time/t_task_total*100:.1f}%)")
        logger.info(f"Budget Optimization: {t_budget_duration:.1f} ms ({t_budget_duration/t_task_total*100:.1f}%)")
        logger.info(f"Response Formatting: {t_formatting_duration:.1f} ms")
        logger.info("-" * 80)
        logger.info(f"TOTAL TASK TIME: {t_task_total:.1f} ms")
        logger.info("=" * 80)
        logger.info("")
        logger.info("SEARCH STATISTICS")
        logger.info("=" * 80)
        logger.info(f"Total RELEVANT Products Retrieved: {total_products_retrieved}")
        logger.info("=" * 80)
        logger.info("")
        logger.info("PER-PRODUCT BREAKDOWN")
        logger.info("=" * 80)
        for item_perf in perf_items:
            logger.info(f"{item_perf['name']}")
            logger.info(f"  Search + Validation: {item_perf['search_ms']:.1f} ms")
            logger.info(f"  RELEVANT products: {item_perf['retrieved']}")
        logger.info("=" * 80)
        
        return response

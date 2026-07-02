"""
Budget Optimizer — Product Discovery Mode with Budget Optimization
====================================================================
Selects the best combination of products across all kit items that maximizes
total recommendation score while making efficient use of the available budget.

Algorithm:
    1. Score all products using multiple factors (search relevance, validation, profile, price)
    2. Keep top N candidates per item (e.g., 5) for optimization
    3. Use dynamic programming to find optimal product combination:
       - Maximize total recommendation score across all items
       - Never exceed user's budget
       - Satisfy all mandatory item constraints
    4. If budget remains, upgrade products to higher-quality alternatives
    5. Return full ranked list per item for user browsing/swapping

Key Improvements over Previous Version:
    - Budget is an optimization objective, not just a constraint
    - Considers product combinations across items, not greedy per-item selection
    - Makes better use of available budget by finding optimal trade-offs
    - Selected total reflects optimized combination, not just cheapest picks
"""
import logging
from typing import List, Dict, Optional, Tuple
from models.schemas import TaskItem, Product

logger = logging.getLogger(__name__)


def _compute_savings(product: Product) -> Product:
    """Attach savings and discount_percent to a product if MRP is available."""
    if product.mrp and product.mrp > product.price:
        product.savings = round(product.mrp - product.price, 2)
        product.discount_percent = int(round((product.savings / product.mrp) * 100))
    else:
        product.savings = None
        product.discount_percent = None
    return product


class BudgetOptimizer:
    """
    Greedy budget optimizer — product discovery mode.

    Returns a full ranked list per item for browsing, plus a
    recommended pick that fits within budget.
    """

    def __init__(self):
        self._product_scores: Dict[str, float] = {}

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def optimize(self, items: List[TaskItem], budget: float, user_profile: Optional[Dict[str, bool]] = None) -> Dict:
        """
        Optimize product selection within budget using dynamic programming.
        
        Maximizes total recommendation score while staying within budget.
        Considers combinations across all items to find the best allocation.

        Returns:
            items:            Updated TaskItem list with recommended picks
            total_cost:       Sum of selected product prices (optimized)
            budget_remaining: budget - total_cost
            within_budget:    True if total_cost <= budget
            success:          False only if mandatory items cannot be satisfied
            message:          Error description if success=False
        """
        logger.info("=" * 80)
        logger.info(f"BUDGET OPTIMIZATION START")
        logger.info(f"Budget: ₹{budget}")
        logger.info(f"Items: {len(items)} ({sum(1 for i in items if i.mandatory)} mandatory)")
        logger.info("=" * 80)
        
        self._product_scores.clear()

        mandatory_items = [i for i in items if i.mandatory]
        optional_items  = [i for i in items if not i.mandatory]

        # Guard: mandatory items must have at least one product
        for item in mandatory_items:
            if not item.products:
                msg = f"No products found for mandatory item: {item.name}"
                logger.error(msg)
                return {
                    "success": False, 
                    "message": msg,
                    "items": items, 
                    "total_cost": None,
                    "within_budget": False, 
                    "budget_remaining": None,
                    "minimum_budget_required": None
                }

        # Score all products
        self._score_all_products(items, user_profile=user_profile, has_budget=True)

        # Keep top N candidates per item for optimization (e.g., 5)
        TOP_N_CANDIDATES = 5
        
        logger.info(f"Keeping top {TOP_N_CANDIDATES} candidates per item for optimization")
        
        optimization_items = []
        for item in items:
            # Get top N scored products for this item
            sorted_products = sorted(
                item.products,
                key=lambda p: self._get_score(p),
                reverse=True
            )
            top_candidates = sorted_products[:TOP_N_CANDIDATES]
            
            if not top_candidates:
                if item.mandatory:
                    msg = f"No products available for mandatory item: {item.name}"
                    logger.error(msg)
                    return {
                        "success": False, 
                        "message": msg,
                        "items": items, 
                        "total_cost": None,
                        "within_budget": False, 
                        "budget_remaining": None,
                        "minimum_budget_required": None
                    }
                continue
            
            optimization_items.append({
                'item': item,
                'candidates': top_candidates,
                'mandatory': item.mandatory
            })
            
            logger.info(f"  {item.name}: {len(top_candidates)} candidates "
                       f"(₹{top_candidates[-1].price:.0f} - ₹{top_candidates[0].price:.0f})")

        # Run optimization to find best product combination
        logger.info("-" * 80)
        logger.info("Running optimization algorithm...")
        
        selection = self._optimize_selection(optimization_items, budget)
        
        if selection is None:
            # Cannot satisfy mandatory items within budget
            min_cost = sum(
                min(opt_item['candidates'], key=lambda p: p.price).price
                for opt_item in optimization_items
                if opt_item['mandatory']
            )
            msg = (f"Cannot satisfy all mandatory items within budget. "
                   f"Minimum required: ₹{min_cost:.2f}, Available: ₹{budget:.2f}")
            logger.error(msg)
            return {
                "success": False, 
                "message": msg,
                "items": items, 
                "total_cost": None,
                "within_budget": False, 
                "budget_remaining": None,
                "minimum_budget_required": round(min_cost, 2)
            }
        
        # Extract selected products and calculate total
        total_cost = 0.0
        total_score = 0.0
        selected_by_item = {}
        
        logger.info("-" * 80)
        logger.info("APPLYING OPTIMIZED SELECTION TO ITEMS:")
        for item_name, product in selection.items():
            selected_by_item[item_name] = product
            total_cost += product.price
            total_score += self._get_score(product)
            logger.info(f"✓ {item_name}:")
            logger.info(f"    Product ID: {product.product_id}")
            logger.info(f"    Name: {product.name}")
            logger.info(f"    Price: ₹{product.price:.2f}")
            logger.info(f"    Optimizer Score: {self._get_score(product):.4f}")
        
        budget_remaining = round(budget - total_cost, 2)
        
        logger.info("-" * 80)
        logger.info(f"Optimization complete:")
        logger.info(f"  Budget:           ₹{budget:.2f}")
        logger.info(f"  Selected total:   ₹{total_cost:.2f}")
        logger.info(f"  Remaining:        ₹{budget_remaining:.2f}")
        logger.info(f"  Budget utilization: {(total_cost/budget*100):.1f}%")
        logger.info(f"  Total score:      {total_score:.4f}")
        logger.info("=" * 80)

        # Build updated items with selections
        updated_items = []
        
        logger.info("-" * 80)
        logger.info("BUILDING RESPONSE WITH OPTIMIZED SELECTIONS:")
        logger.info("(Verifying that item.recommended is set to optimizer's choice)")
        logger.info("")
        
        for item in items:
            selected_product = selected_by_item.get(item.name)
            
            # Rank all products for this item
            ranked = self._rank_products(item.products)
            
            if selected_product:
                # CRITICAL: Set recommended to the optimizer's selected product
                item.recommended = _compute_savings(selected_product)
                item.products = ranked[:8]  # Keep top 8 for user browsing
                item.budget_allocated = selected_product.price
                
                # Verify the assignment worked
                if item.recommended.product_id != selected_product.product_id:
                    logger.error(f"  ❌ {item.name}: MISMATCH!")
                    logger.error(f"     Expected: {selected_product.product_id}")
                    logger.error(f"     Got: {item.recommended.product_id}")
                else:
                    logger.info(f"  ✓ {item.name}:")
                    logger.info(f"     Recommended set to: {selected_product.product_id}")
                    logger.info(f"     Product: {selected_product.name}")
                    logger.info(f"     Price: ₹{selected_product.price:.2f}")
                    
                    # Check if it's the first ranked product or a different one
                    if ranked and ranked[0].product_id == selected_product.product_id:
                        logger.info(f"     (This is the #1 ranked product)")
                    else:
                        first_ranked_id = ranked[0].product_id if ranked else "None"
                        logger.info(f"     (Optimizer chose this over #1 ranked: {first_ranked_id})")
            else:
                # Optional item not selected
                item.recommended = None
                item.products = ranked[:8]
                item.budget_allocated = 0
                logger.info(f"  ○ {item.name}: No selection (optional item skipped)")
            
            logger.info("")
            updated_items.append(item)
        
        logger.info("-" * 80)

        return {
            "success":          True,
            "message":          None,
            "items":            updated_items,
            "total_cost":       round(total_cost, 2),
            "within_budget":    total_cost <= budget,
            "budget_remaining": budget_remaining,
            "minimum_budget_required": None  # Only set on failure
        }
    
    def _optimize_selection(
        self,
        optimization_items: List[Dict],
        budget: float
    ) -> Optional[Dict[str, Product]]:
        """
        Find optimal product combination that maximizes total score within budget.
        
        Uses dynamic programming approach to explore product combinations.
        
        Args:
            optimization_items: List of dicts with 'item', 'candidates', 'mandatory'
            budget: Total budget available
        
        Returns:
            Dict mapping item_name -> selected Product, or None if impossible
        """
        logger.info(">>> ENTERING _optimize_selection()")
        logger.info(f"   Budget: ₹{budget:.2f}")
        logger.info(f"   Items to optimize: {len(optimization_items)}")
        
        # Separate mandatory and optional items
        mandatory = [opt for opt in optimization_items if opt['mandatory']]
        optional = [opt for opt in optimization_items if not opt['mandatory']]
        
        logger.info(f"   Mandatory items: {len(mandatory)}")
        logger.info(f"   Optional items: {len(optional)}")
        
        # First, check if we can satisfy all mandatory items
        min_mandatory_cost = sum(
            min(opt['candidates'], key=lambda p: p.price).price
            for opt in mandatory
        )
        
        logger.info(f"   Minimum mandatory cost: ₹{min_mandatory_cost:.2f}")
        
        if min_mandatory_cost > budget:
            logger.error(f"Cannot satisfy mandatory items: need ₹{min_mandatory_cost:.2f}, have ₹{budget:.2f}")
            return None
        
        # Log all candidates for debugging
        logger.info("-" * 80)
        logger.info("CANDIDATES AVAILABLE FOR OPTIMIZATION:")
        for opt_item in optimization_items:
            item_name = opt_item['item'].name
            candidates = opt_item['candidates']
            logger.info(f"\n{item_name} ({'Mandatory' if opt_item['mandatory'] else 'Optional'}):")
            for idx, product in enumerate(candidates, 1):
                score = self._get_score(product)
                logger.info(f"  {idx}. {product.product_id} | {product.name} | ₹{product.price:.2f} | score={score:.3f}")
        logger.info("-" * 80)
        
        # Use recursive backtracking with memoization to find optimal combination
        logger.info("Starting recursive optimization search...")
        logger.info("Exploring combinations (showing complete valid combinations):")
        
        best_selection = self._find_best_combination(
            optimization_items=optimization_items,
            budget=budget,
            current_index=0,
            current_selection={},
            current_cost=0.0,
            current_score=0.0
        )
        
        if best_selection:
            final_cost = sum(p.price for p in best_selection.values())
            final_score = sum(self._get_score(p) for p in best_selection.values())
            logger.info("-" * 80)
            logger.info(f"🏆 BEST COMBINATION FOUND:")
            for item_name, product in best_selection.items():
                logger.info(f"   {item_name}: {product.product_id} | {product.name} | ₹{product.price:.2f}")
            logger.info(f"   Total Cost: ₹{final_cost:.2f}")
            logger.info(f"   Total Score: {final_score:.3f}")
            logger.info(f"   Budget Utilization: {(final_cost/budget*100):.1f}%")
            logger.info("-" * 80)
        else:
            logger.error("NO VALID COMBINATION FOUND")
        
        logger.info("<<< EXITING _optimize_selection()")
        
        return best_selection
    
    def _find_best_combination(
        self,
        optimization_items: List[Dict],
        budget: float,
        current_index: int,
        current_selection: Dict[str, Product],
        current_cost: float,
        current_score: float
    ) -> Optional[Dict[str, Product]]:
        """
        Recursively find the best product combination using backtracking.
        
        This explores the search space efficiently by:
        1. Always selecting mandatory items (trying all candidate options)
        2. For optional items, trying both selection and skip
        3. Pruning branches that exceed budget
        4. Tracking the best valid combination found
        5. Tie-breaker: If scores equal, prefer higher total cost
        """
        # Base case: processed all items
        if current_index >= len(optimization_items):
            # Check if all mandatory items were selected
            for opt_item in optimization_items:
                if opt_item['mandatory'] and opt_item['item'].name not in current_selection:
                    return None  # Invalid - missing mandatory item
            
            # Log complete combination with detailed breakdown
            combo_cost = sum(p.price for p in current_selection.values())
            combo_score = sum(self._get_score(p) for p in current_selection.values())
            combo_details = []
            for name, p in current_selection.items():
                combo_details.append(f"{name}={p.product_id}(₹{p.price:.0f},s={self._get_score(p):.3f})")
            combo_str = " | ".join(combo_details)
            logger.debug(f"   ✓ Valid combination: {combo_str} → Total: ₹{combo_cost:.2f}, Score: {combo_score:.4f}")
            
            return current_selection.copy()
        
        opt_item = optimization_items[current_index]
        item_name = opt_item['item'].name
        candidates = opt_item['candidates']
        is_mandatory = opt_item['mandatory']
        
        best_result = None
        best_score = -1.0
        best_cost = 0.0
        
        if is_mandatory:
            # Try each candidate for this mandatory item
            for product in candidates:
                new_cost = current_cost + product.price
                
                if new_cost <= budget:
                    new_selection = current_selection.copy()
                    new_selection[item_name] = product
                    new_score = current_score + self._get_score(product)
                    
                    result = self._find_best_combination(
                        optimization_items,
                        budget,
                        current_index + 1,
                        new_selection,
                        new_cost,
                        new_score
                    )
                    
                    if result is not None:
                        result_score = sum(self._get_score(p) for p in result.values())
                        result_cost = sum(p.price for p in result.values())
                        
                        # Update best if: higher score, OR same score but higher cost (tie-breaker)
                        if result_score > best_score or (result_score == best_score and result_cost > best_cost):
                            best_score = result_score
                            best_cost = result_cost
                            best_result = result
        else:
            # Optional item: try selecting best affordable candidate OR skip
            
            # Option 1: Skip this optional item
            result_skip = self._find_best_combination(
                optimization_items,
                budget,
                current_index + 1,
                current_selection,
                current_cost,
                current_score
            )
            
            if result_skip is not None:
                skip_score = sum(self._get_score(p) for p in result_skip.values())
                skip_cost = sum(p.price for p in result_skip.values())
                
                if skip_score > best_score or (skip_score == best_score and skip_cost > best_cost):
                    best_score = skip_score
                    best_cost = skip_cost
                    best_result = result_skip
            
            # Option 2: Try each candidate for this optional item
            for product in candidates:
                new_cost = current_cost + product.price
                
                if new_cost <= budget:
                    new_selection = current_selection.copy()
                    new_selection[item_name] = product
                    new_score = current_score + self._get_score(product)
                    
                    result = self._find_best_combination(
                        optimization_items,
                        budget,
                        current_index + 1,
                        new_selection,
                        new_cost,
                        new_score
                    )
                    
                    if result is not None:
                        result_score = sum(self._get_score(p) for p in result.values())
                        result_cost = sum(p.price for p in result.values())
                        
                        # Update best if: higher score, OR same score but higher cost (tie-breaker)
                        if result_score > best_score or (result_score == best_score and result_cost > best_cost):
                            best_score = result_score
                            best_cost = result_cost
                            best_result = result
        
        return best_result

    # ─────────────────────────────────────────────────────────────────────────
    # No-budget mode (discovery only — no recommended pick needed)
    # ─────────────────────────────────────────────────────────────────────────

    def discover(self, items: List[TaskItem], user_profile: Optional[Dict[str, bool]] = None) -> List[TaskItem]:
        """
        Rank products within each item without a budget constraint.
        Sets recommended = top-rated product, keeps full list for browsing.
        """
        self._score_all_products(items, user_profile=user_profile, has_budget=False)
        for item in items:
            ranked = self._rank_products(item.products)
            item.products = ranked[:8]
            if ranked:
                item.recommended      = _compute_savings(ranked[0])
                item.budget_allocated = ranked[0].price
            else:
                item.recommended      = None
                item.budget_allocated = None
        return items

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _score_all_products(self, items: List[TaskItem], user_profile: Optional[Dict[str, bool]] = None, has_budget: bool = False) -> None:
        logger.info("=" * 80)
        logger.info("COMPUTING OPTIMIZER SCORES FOR ALL PRODUCTS")
        logger.info("=" * 80)
        
        all_products = [p for item in items for p in item.products]
        if not all_products:
            logger.warning("No products to score!")
            return
        
        max_price = max(p.price for p in all_products) or 1.0
        logger.info(f"Max price across all products: ₹{max_price:.2f}")
        logger.info(f"User profile: {user_profile}")
        logger.info(f"Has budget: {has_budget}")
        logger.info("")
        
        for item in items:
            logger.info(f"Item: {item.name}")
            for product in item.products:
                score = self._score_product(product, max_price, user_profile, has_budget)
                self._product_scores[product.product_id] = score
                
                # Log detailed scoring breakdown
                logger.info(f"  Product: {product.product_id} | {product.name}")
                logger.info(f"    Price: ₹{product.price:.2f}")
                logger.info(f"    similarity (hybrid search score): {product.similarity}")
                logger.info(f"    validation_confidence: {product.validation_confidence}")
                logger.info(f"    profile_score: {product.profile_score}")
                logger.info(f"    recommendation_score: {product.recommendation_score}")
                logger.info(f"    → COMPUTED OPTIMIZER SCORE: {score:.4f}")
                logger.info("")
        
        logger.info("=" * 80)

    def _score_product(self, product: Product, max_price: float, user_profile: Optional[Dict[str, bool]] = None, has_budget: bool = False) -> float:
        """
        Compute optimizer score for a product.
        
        FORMULA: score = 0.6*search + 0.3*validation + 0.1*profile
        
        This score measures product quality/relevance only.
        Budget is enforced as a constraint in _find_best_combination().
        
        When scores are equal, tie-breaker prefers higher total cost
        (better use of available budget).
        """
        # Extract component scores from product attributes
        # similarity = hybrid search score (from semantic + keyword ranking)
        search_score = min(1.0, max(0.0, product.similarity or 0.5))
        
        # validation_confidence = LLM validation confidence
        validation_score = min(1.0, max(0.0, product.validation_confidence or 0.5))
        
        # profile_score = user profile match (kids/beginner/etc)
        profile_score_val = min(1.0, max(0.0, product.profile_score or 1.0))
        
        final_score = (0.6 * search_score
                      + 0.3 * validation_score
                      + 0.1 * profile_score_val)
        
        return final_score

    def _get_score(self, product: Product) -> float:
        return self._product_scores.get(product.product_id, 0.0)

    def _utility(self, product: Product) -> float:
        score = self._get_score(product)
        return score / product.price if product.price > 0 else 0.0

    def _rank_products(self, products: List[Product]) -> List[Product]:
        """Return products sorted by score descending, with savings attached."""
        ranked = sorted(products, key=lambda p: self._get_score(p), reverse=True)
        return [_compute_savings(p) for p in ranked]

    def _pick_best(
        self, item: TaskItem, available: float
    ) -> Tuple[Optional[Product], float]:
        """Pick highest-scored product within available budget."""
        sorted_products = sorted(
            item.products,
            key=lambda p: self._get_score(p),
            reverse=True
        )
        for product in sorted_products:
            if product.price <= available:
                return product, product.price

        # Last resort: cheapest, only if it fits
        cheapest = min(item.products, key=lambda p: p.price)
        if cheapest.price <= available:
            return cheapest, cheapest.price

        return None, 0

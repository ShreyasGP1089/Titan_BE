"""
Budget Optimizer — Product Discovery Mode
==========================================
Selects the best product per kit item within budget (recommended),
while also returning the full ranked list so the user can browse
and swap to any option they prefer.

Algorithm:
    1. Score all products: 0.5*rating + 0.3*semantic + 0.2*price_efficiency
    2. Mandatory items: pick highest-scored product within budget
    3. Optional items: add by utility (score/price) if budget allows
    4. Each item keeps its full ranked product list for discovery
    5. budget_remaining = budget - total_cost of recommended picks
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

    def optimize(self, items: List[TaskItem], budget: float) -> Dict:
        """
        Optimize product selection within budget.

        Returns:
            items:            Updated TaskItem list.
                              Each item has:
                                recommended — best pick within budget
                                products    — full ranked discovery list
                                budget_allocated — price of recommended pick
            total_cost:       Sum of recommended pick prices
            budget_remaining: budget - total_cost
            within_budget:    True if total_cost <= budget
            success:          False only if a mandatory item has no products at all
            message:          Error description if success=False
        """
        logger.info(f"Budget optimization start — budget=₹{budget}")
        self._product_scores.clear()

        mandatory_items = [i for i in items if i.mandatory]
        optional_items  = [i for i in items if not i.mandatory]

        # Guard: mandatory items must have at least one product
        for item in mandatory_items:
            if not item.products:
                msg = f"No products found for mandatory item: {item.name}"
                logger.error(msg)
                return {
                    "success": False, "message": msg,
                    "items": items, "total_cost": None,
                    "within_budget": False, "budget_remaining": None
                }

        # Score every product
        self._score_all_products(items)

        # ── Mandatory items ───────────────────────────────────────────────
        mandatory_results = []
        total_cost = 0.0

        min_mandatory_cost = sum(
            min(i.products, key=lambda p: p.price).price
            for i in mandatory_items
        )
        if min_mandatory_cost > budget * 0.7:
            logger.info(f"Tight budget — min mandatory cost ₹{min_mandatory_cost}")

        for idx, item in enumerate(mandatory_items):
            # Reserve budget for remaining mandatory items
            min_remaining = sum(
                min(mandatory_items[j].products, key=lambda p: p.price).price
                for j in range(idx + 1, len(mandatory_items))
            )
            available = (budget - total_cost) - min_remaining

            recommended, cost = self._pick_best(item, available)

            if recommended is None:
                cheapest = min(item.products, key=lambda p: p.price)
                msg = (
                    f"Budget too tight for mandatory item '{item.name}'. "
                    f"Cheapest option: ₹{cheapest.price}"
                )
                logger.error(msg)
                return {
                    "success": False, "message": msg,
                    "items": items, "total_cost": None,
                    "within_budget": False, "budget_remaining": None
                }

            mandatory_results.append({"item": item, "recommended": recommended, "cost": cost})
            total_cost += cost
            logger.info(f"✓ Mandatory '{item.name}' → {recommended.name} (₹{cost})")

        # ── Optional items ────────────────────────────────────────────────
        optional_results = []
        remaining = budget - total_cost

        if remaining > 0 and optional_items:
            logger.info(f"Optional selection — ₹{remaining} remaining")

            candidates = []
            for item in optional_items:
                for product in item.products:
                    if product.price <= remaining:
                        candidates.append({
                            "item": item,
                            "product": product,
                            "utility": self._utility(product),
                            "cost": product.price
                        })
            candidates.sort(key=lambda x: x["utility"], reverse=True)

            picked_names = set()
            for c in candidates:
                name = c["item"].name
                if name in picked_names:
                    continue
                if c["cost"] <= remaining:
                    optional_results.append({"item": c["item"], "recommended": c["product"], "cost": c["cost"]})
                    picked_names.add(name)
                    remaining -= c["cost"]
                    total_cost += c["cost"]
                    logger.info(f"✓ Optional '{name}' → {c['product'].name} (₹{c['cost']})")

        # ── Build output items ────────────────────────────────────────────
        updated_items = []

        for result in mandatory_results:
            item = result["item"]
            rec  = _compute_savings(result["recommended"])
            # Full ranked list with savings attached, recommended first
            ranked = self._rank_products(item.products)
            item.recommended     = rec
            item.products        = ranked
            item.budget_allocated = result["cost"]
            updated_items.append(item)

        for item in optional_items:
            sel = next((r for r in optional_results if r["item"].name == item.name), None)
            ranked = self._rank_products(item.products)
            if sel:
                item.recommended      = _compute_savings(sel["recommended"])
                item.products         = ranked
                item.budget_allocated = sel["cost"]
            else:
                item.recommended      = None
                item.products         = ranked
                item.budget_allocated = 0
            updated_items.append(item)

        within_budget    = total_cost <= budget
        budget_remaining = round(budget - total_cost, 2)

        logger.info("=" * 60)
        logger.info(f"Optimization complete:")
        logger.info(f"  Budget:    ₹{budget}")
        logger.info(f"  Total:     ₹{total_cost}")
        logger.info(f"  Remaining: ₹{budget_remaining}")
        logger.info("=" * 60)

        return {
            "success":          True,
            "message":          None,
            "items":            updated_items,
            "total_cost":       total_cost,
            "within_budget":    within_budget,
            "budget_remaining": budget_remaining,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # No-budget mode (discovery only — no recommended pick needed)
    # ─────────────────────────────────────────────────────────────────────────

    def discover(self, items: List[TaskItem]) -> List[TaskItem]:
        """
        Rank products within each item without a budget constraint.
        Sets recommended = top-rated product, keeps full list for browsing.
        """
        self._score_all_products(items)
        for item in items:
            ranked = self._rank_products(item.products)
            item.products = ranked
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

    def _score_all_products(self, items: List[TaskItem]) -> None:
        all_products = [p for item in items for p in item.products]
        if not all_products:
            return
        max_price = max(p.price for p in all_products) or 1.0
        for item in items:
            for product in item.products:
                self._product_scores[product.product_id] = self._score_product(product, max_price)

    def _score_product(self, product: Product, max_price: float) -> float:
        """score = 0.5*rating + 0.3*semantic + 0.2*price_efficiency"""
        rating_score = (product.rating / 5.0) if product.rating else 0.0
        semantic     = min(1.0, max(0.0, product.similarity or 0.5))
        price_eff    = max(0.0, 1.0 - (product.price / max_price)) if max_price > 0 else 0.0
        return 0.5 * rating_score + 0.3 * semantic + 0.2 * price_eff

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

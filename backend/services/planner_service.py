"""
Dynamic Task Planner Service
Generates searchable product names dynamically using SLM reasoning
"""
import logging
import os
import requests
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class PlannerService:
    """Service for dynamic task planning using SLM"""
    
    def __init__(self):
        """Initialize planner service with local model URL"""
        self.base_url = os.getenv("LOCAL_MODEL_URL", "http://localhost:8000")
        logger.info(f"PlannerService initialized: {self.base_url}")
    
    def plan_task(
        self,
        activity: str,
        sport: str,
        user_query: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Generate a dynamic task plan using the SLM planner.
        
        Args:
            activity: The activity type (e.g., "Golf", "Running")
            sport: The sport name
            user_query: Optional user query for context
        
        Returns:
            Dict with:
                - items: List of planned items with name, mandatory, keywords
                - confidence: Confidence score (0-1)
            None if planner fails or is unavailable
        """
        try:
            payload = {
                "activity": activity,
                "sport": sport,
                "user_query": user_query or activity
            }
            
            url = f"{self.base_url}/plan-task"
            logger.info(f"Calling dynamic planner at {url}")
            logger.info(f"  Activity: {activity}")
            logger.info(f"  Sport: {sport}")
            logger.info(f"  User Query: {user_query}")
            
            response = requests.post(
                url,
                json=payload,
                timeout=30  # 30 second timeout
            )
            
            if response.status_code != 200:
                logger.error(f"Planner returned status {response.status_code}: {response.text}")
                return None
            
            result = response.json()
            
            # Validate response structure
            if "items" not in result:
                logger.error("Planner response missing 'items' field")
                return None
            
            if not isinstance(result["items"], list):
                logger.error("Planner 'items' field is not a list")
                return None
            
            if len(result["items"]) == 0:
                logger.warning("Planner returned empty items list")
                return None
            
            # Log the plan
            logger.info("=" * 80)
            logger.info("DYNAMIC PLANNER RESULT")
            logger.info(f"  Generated {len(result['items'])} items:")
            for idx, item in enumerate(result["items"], 1):
                mandatory_str = "mandatory" if item.get("mandatory", False) else "optional"
                keywords_str = ", ".join(item.get("keywords", []))
                logger.info(f"    {idx}. {item['name']} ({mandatory_str})")
                logger.info(f"       Keywords: {keywords_str}")
            logger.info(f"  Confidence: {result.get('confidence', 0.0):.2f}")
            logger.info("=" * 80)
            
            return result
            
        except requests.Timeout:
            logger.error("Planner request timed out")
            return None
        except requests.ConnectionError:
            logger.error("Could not connect to planner service")
            return None
        except Exception as e:
            logger.error(f"Error calling planner: {e}")
            return None

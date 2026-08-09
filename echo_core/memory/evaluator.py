"""
ECHO-7 Importance Evaluator
Paper Section 3.3: Memory Evaluation
"""

import re
from typing import Tuple

class MemoryEvaluator:
    """
    Evaluates importance of messages for memory tier assignment.
    """
    
    def __init__(self):
        # Primary importance patterns (moderate weight)
        self.primary_patterns = [
            (r'\b(project|decision|prefer|remember|system|setup|config|architecture)\b', 0.3),
            (r'\bI (am|work|use|build|create|have|need|want|decided|prefer)\b', 0.25),
            (r'[A-Z][a-z]+( project| system| app| tool| framework)', 0.25),
            (r'\b(goal|objective|plan|future|schedule|deadline)\b', 0.25),
            (r'\b(important|critical|essential|key|main|primary)\b', 0.25),
            (r'\b(never|always|usually|prefer|like|dislike)\b', 0.2),
            (r'\b(remember|save|store|note|decided|building|called)\b', 0.25),
        ]
        
        # Secondary patterns (low weight)
        self.secondary_patterns = [
            (r'\b(update|progress|status|current|working)\b', 0.1),
            (r'\b(task|item|step)\b', 0.05),
        ]
        
        # Low-importance patterns (reduce score)
        self.low_patterns = [
            (r'^\b(hi|hello|hey|thanks|ok|okay|yes|no|bye)\b', 0.3),
            (r'\?$', 0.1),
            (r'\b(weather|time|date|news|joke|funny|regular)\b', 0.15),
            (r'\b(haha|lol|okay|sure|fine)\b', 0.15),
        ]
    
    def evaluate(self, message: str) -> Tuple[float, str]:
        """Returns: (importance_score, suggested_memory_type)"""
        message_lower = message.lower()
        score = 0.0
        
        # Primary patterns
        for pattern, weight in self.primary_patterns:
            if re.search(pattern, message_lower):
                score += weight
        
        # Secondary patterns
        for pattern, weight in self.secondary_patterns:
            if re.search(pattern, message_lower):
                score += weight
        
        # Low patterns (penalty)
        for pattern, weight in self.low_patterns:
            if re.search(pattern, message_lower):
                score -= weight
        
        # Length bonus (only for longer messages)
        word_count = len(message.split())
        if word_count > 15:
            score += 0.15
        if word_count > 25:
            score += 0.15
        
        # Clamp
        score = max(0.0, min(1.0, score))
        
        # Tier assignment (threshold 0.5 for important)
        if score >= 0.5:
            suggested_type = "important"
        elif score >= 0.25:
            suggested_type = "recent"
        else:
            suggested_type = "working"
        
        return score, suggested_type
    
    def should_store_permanently(self, message: str) -> bool:
        """Returns True if message should be stored in Important memory"""
        score, _ = self.evaluate(message)
        return score >= 0.5
    
    def get_importance_category(self, message: str) -> str:
        """Returns: 'low', 'medium', 'high'"""
        score, _ = self.evaluate(message)
        if score >= 0.5:
            return "high"
        elif score >= 0.25:
            return "medium"
        else:
            return "low"
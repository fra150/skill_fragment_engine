"""Transfer learning service for improved fragment adaptation."""

from __future__ import annotations

import structlog
from collections import defaultdict
from datetime import datetime
from typing import Any
from uuid import UUID

from skill_fragment_engine.core.config import get_settings

logger = structlog.get_logger(__name__)


class AdaptationPattern:
    """Pattern learned from successful adaptations."""
    
    def __init__(
        self,
        pattern_id: str,
        task_type: str,
        input_pattern: str,
        output_transform: dict[str, Any],
        success_count: int = 0,
        failure_count: int = 0,
        last_used: datetime | None = None,
    ):
        self.pattern_id = pattern_id
        self.task_type = task_type
        self.input_pattern = input_pattern
        self.output_transform = output_transform
        self.success_count = success_count
        self.failure_count = failure_count
        self.last_used = last_used
    
    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0


class TransferLearningService:
    """
    Service for transfer learning to improve fragment adaptation.
    
    Features:
    - Learn successful adaptation patterns
    - Apply learned patterns to new adaptations
    - Track pattern success rates
    - Suggest optimal transformations
    """
    
    def __init__(self):
        self.settings = get_settings()
        
        # Pattern storage
        self._patterns: dict[str, list[AdaptationPattern]] = defaultdict(list)
        
        # Parameter mappings (learned from successful adaptations)
        self._parameter_mappings: dict[str, dict[str, str]] = defaultdict(dict)
        
        # Context transformation rules
        self._context_transforms: dict[str, dict[str, Any]] = defaultdict(dict)
        
        # Minimum samples before using pattern
        self._min_samples_for_pattern = 3
    
    def learn_from_adaptation(
        self,
        task_type: str,
        original_input: dict[str, Any],
        adapted_output: Any,
        parameters: dict[str, Any],
        context: dict[str, Any],
        success: bool,
    ) -> None:
        """
        Learn from a completed adaptation to improve future adaptations.
        
        Args:
            task_type: Type of task (e.g., "code_generation")
            original_input: Original input parameters
            adapted_output: The adapted result
            parameters: Parameters used for adaptation
            context: Context information
            success: Whether the adaptation was successful
        """
        # Extract patterns from the adaptation
        pattern_key = self._extract_pattern_key(task_type, parameters, context)
        
        # Find or create pattern
        patterns = self._patterns.get(task_type, [])
        pattern = next((p for p in patterns if p.input_pattern == pattern_key), None)
        
        if pattern:
            # Update existing pattern
            if success:
                pattern.success_count += 1
            else:
                pattern.failure_count += 1
            pattern.last_used = datetime.utcnow()
        else:
            # Create new pattern
            transform = self._extract_transformation(original_input, parameters, adapted_output)
            pattern = AdaptationPattern(
                pattern_id=str(UUID()),
                task_type=task_type,
                input_pattern=pattern_key,
                output_transform=transform,
                success_count=1 if success else 0,
                failure_count=0 if success else 1,
                last_used=datetime.utcnow(),
            )
            self._patterns[task_type].append(pattern)
        
        # Learn parameter mappings
        self._learn_parameter_mappings(task_type, original_input, parameters, context)
        
        logger.debug(
            "adaptation_learned",
            task_type=task_type,
            pattern_key=pattern_key[:50],
            success=success,
        )
    
    def _extract_pattern_key(
        self,
        task_type: str,
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> str:
        """Extract a pattern key from parameters and context."""
        # Combine relevant keys into a pattern signature
        relevant_keys = []
        
        # Add task-specific relevant keys
        if task_type == "code_generation":
            relevant_keys = ["language", "style", "framework"]
        elif task_type == "text_summarization":
            relevant_keys = ["length", "tone", "focus"]
        elif task_type == "translation":
            relevant_keys = ["source_language", "target_language", "formality"]
        else:
            relevant_keys = list(parameters.keys())[:3]
        
        # Build pattern string
        pattern_parts = []
        for key in relevant_keys:
            if key in parameters:
                pattern_parts.append(f"{key}={parameters[key]}")
            elif key in context:
                pattern_parts.append(f"{key}={context[key]}")
        
        return "|".join(pattern_parts) if pattern_parts else "default"
    
    def _extract_transformation(
        self,
        original_input: dict[str, Any],
        parameters: dict[str, Any],
        adapted_output: Any,
    ) -> dict[str, Any]:
        """Extract the transformation applied during adaptation."""
        # Simple transformation extraction
        # In production, this would be more sophisticated
        return {
            "parameter_changes": list(parameters.keys()),
            "output_type": type(adapted_output).__name__,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def _learn_parameter_mappings(
        self,
        task_type: str,
        original_input: dict[str, Any],
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> None:
        """Learn mappings between input parameters and adaptation parameters."""
        for input_key, input_value in original_input.items():
            if input_key in parameters:
                # Learn this mapping
                mapping_key = f"{task_type}:{input_key}"
                param_value = parameters[input_key]
                
                if mapping_key not in self._parameter_mappings:
                    self._parameter_mappings[mapping_key] = {}
                
                mapping = self._parameter_mappings[mapping_key]
                if input_value not in mapping:
                    mapping[input_value] = {}
                
                if param_value not in mapping[input_value]:
                    mapping[input_value][param_value] = 0
                
                mapping[input_value][param_value] += 1
    
    async def suggest_adaptation(
        self,
        task_type: str,
        original_parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Suggest adaptation parameters based on learned patterns.
        
        Args:
            task_type: Type of task
            original_parameters: Original parameters to adapt
            context: Context information
            
        Returns:
            Suggested adaptation parameters and transformations
        """
        suggestions = {
            "parameter_mappings": {},
            "confidence": 0.0,
            "patterns_used": [],
        }
        
        # Find relevant patterns
        patterns = self._patterns.get(task_type, [])
        pattern_key = self._extract_pattern_key(task_type, original_parameters, context)
        
        # Find matching pattern with highest success rate
        best_pattern = None
        best_rate = 0.0
        
        for pattern in patterns:
            if self._calculate_pattern_similarity(pattern.input_pattern, pattern_key) > 0.5:
                if pattern.success_rate > best_rate and pattern.success_count >= self._min_samples_for_pattern:
                    best_pattern = pattern
                    best_rate = pattern.success_rate
        
        if best_pattern:
            suggestions["patterns_used"].append(best_pattern.pattern_id)
            suggestions["confidence"] = best_rate
            
            # Extract parameter mappings from pattern
            for key, value in original_parameters.items():
                mapping_key = f"{task_type}:{key}"
                if mapping_key in self._parameter_mappings:
                    mappings = self._parameter_mappings[mapping_key]
                    if value in mappings:
                        # Get most common mapped value
                        mapped_values = mappings[value]
                        most_common = max(mapped_values.items(), key=lambda x: x[1])
                        suggestions["parameter_mappings"][key] = most_common[0]
        
        # Add context-based suggestions
        context_suggestions = self._get_context_suggestions(task_type, context)
        suggestions["parameter_mappings"].update(context_suggestions)
        
        logger.debug(
            "adaptation_suggested",
            task_type=task_type,
            confidence=suggestions["confidence"],
            patterns_used=len(suggestions["patterns_used"]),
        )
        
        return suggestions
    
    def _calculate_pattern_similarity(self, pattern1: str, pattern2: str) -> float:
        """Calculate similarity between two pattern keys."""
        parts1 = set(pattern1.split("|"))
        parts2 = set(pattern2.split("|"))
        
        if not parts1 or not parts2:
            return 0.0
        
        intersection = len(parts1 & parts2)
        union = len(parts1 | parts2)
        
        return intersection / union if union > 0 else 0.0
    
    def _get_context_suggestions(
        self,
        task_type: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Get suggestions based on context."""
        suggestions = {}
        
        # For code generation
        if task_type == "code_generation":
            if "language" in context:
                lang = context["language"]
                # Suggest common patterns for language
                if lang in ["python", "javascript"]:
                    suggestions["style"] = "clean"
                elif lang in ["java", "csharp"]:
                    suggestions["style"] = "oop"
        
        # For text tasks
        elif task_type in ["text_summarization", "translation"]:
            if "tone" in context:
                suggestions["tone"] = context["tone"]
            if "formality" in context:
                suggestions["formality"] = context["formality"]
        
        return suggestions
    
    def get_pattern_stats(self, task_type: str | None = None) -> dict[str, Any]:
        """Get statistics about learned patterns."""
        if task_type:
            patterns = self._patterns.get(task_type, [])
        else:
            patterns = [p for p_list in self._patterns.values() for p in p_list]
        
        if not patterns:
            return {
                "total_patterns": 0,
                "average_success_rate": 0.0,
                "patterns_by_task": {},
            }
        
        total = len(patterns)
        avg_rate = sum(p.success_rate for p in patterns) / total
        
        by_task = {}
        for t, p_list in self._patterns.items():
            by_task[t] = {
                "count": len(p_list),
                "avg_success_rate": sum(p.success_rate for p in p_list) / len(p_list) if p_list else 0,
                "total_uses": sum(p.success_count + p.failure_count for p in p_list),
            }
        
        return {
            "total_patterns": total,
            "average_success_rate": round(avg_rate, 3),
            "patterns_by_task": by_task,
        }
    
    def get_top_patterns(self, task_type: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get top patterns for a task type, sorted by success rate."""
        patterns = self._patterns.get(task_type, [])
        
        sorted_patterns = sorted(
            patterns,
            key=lambda p: (p.success_rate, p.success_count),
            reverse=True,
        )
        
        return [
            {
                "pattern_id": p.pattern_id,
                "input_pattern": p.input_pattern,
                "success_rate": round(p.success_rate, 3),
                "success_count": p.success_count,
                "failure_count": p.failure_count,
                "last_used": p.last_used.isoformat() if p.last_used else None,
            }
            for p in sorted_patterns[:limit]
        ]
    
    def clear_old_patterns(self, days_old: int = 90) -> int:
        """Clear patterns that haven't been used recently."""
        cutoff = datetime.utcnow() - datetime.timedelta(days=days_old)
        cleared = 0
        
        for task_type in list(self._patterns.keys()):
            patterns = self._patterns[task_type]
            self._patterns[task_type] = [
                p for p in patterns
                if p.last_used is None or p.last_used > cutoff
            ]
            cleared += len(patterns) - len(self._patterns[task_type])
        
        if cleared > 0:
            logger.info("old_patterns_cleared", count=cleared)
        
        return cleared


# Singleton instance
_transfer_learning_service: TransferLearningService | None = None
def get_transfer_learning_service() -> TransferLearningService:
    """Get or create the transfer learning service singleton."""
    global _transfer_learning_service
    if _transfer_learning_service is None:
        _transfer_learning_service = TransferLearningService()
    return _transfer_learning_service
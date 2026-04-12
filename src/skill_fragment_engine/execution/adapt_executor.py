"""Adapt executor - modifies cached output for new input."""

from __future__ import annotations

import structlog
from uuid import uuid4

from skill_fragment_engine.core.config import get_settings
from skill_fragment_engine.core.models import (
    SkillFragment,
    ExecutionRequest,
    Variant,
    FragmentPattern,
)

logger = structlog.get_logger(__name__)


class AdaptExecutor:
    """
    Executes ADAPT decision.
    Takes a cached fragment and adapts it to the new input context.
    This is the complex case - it may involve:
    - Parameter injection
    - Style modification
    - Structure adjustment
    """

    def __init__(self):
        self.settings = get_settings()

    async def execute(
        self,
        fragment: SkillFragment | None,
        request: ExecutionRequest,
    ) -> tuple[any, str | None]:
        """
        Execute adaptation.

        Args:
            fragment: Fragment to adapt
            request: New input request

        Returns:
            Tuple of (adapted_result, variant_id)
        """
        if fragment is None:
            raise ValueError("Cannot adapt: fragment is None")

        logger.info(
            "adapt_execution",
            fragment_id=fragment.fragment_id,
            task_type=request.task_type,
        )

        # Get the cached output as base
        base_output = fragment.output_schema.result

        # Adapt based on task type
        adapted_output = await self._adapt_output(
            base_output=base_output,
            fragment=fragment,
            request=request,
        )

        # Create variant record
        variant = self._create_variant(
            parent=fragment,
            original_output=base_output,
            adapted_output=adapted_output,
            request=request,
        )

        # Update fragment metrics
        fragment.metrics.adapt_count += 1
        fragment.metrics.total_cost_saved += (
            self.settings.base_execution_cost - self.settings.adaptation_cost
        )

        logger.info(
            "adapt_complete",
            fragment_id=fragment.fragment_id,
            variant_id=variant.variant_id,
        )

        return adapted_output, str(variant.variant_id)

    async def _adapt_output(
        self,
        base_output: any,
        fragment: SkillFragment,
        request: ExecutionRequest,
    ) -> any:
        """
        Adapt the base output to the new input.

        Strategy depends on task type:
        - code_generation: Inject new parameters into generated code
        - text_summarization: Adjust summary length/style
        - translation: Modify tense/style
        - etc.
        """
        task_type = request.task_type

        if task_type == "code_generation":
            return await self._adapt_code(base_output, fragment, request)
        elif task_type == "text_summarization":
            return await self._adapt_summary(base_output, fragment, request)
        elif task_type == "translation":
            return await self._adapt_translation(base_output, fragment, request)
        else:
            # Generic adaptation - return base with minor modifications
            return self._generic_adapt(base_output, request)

    async def _adapt_code(
        self,
        base_output: any,
        fragment: SkillFragment,
        request: ExecutionRequest,
    ) -> any:
        """
        Adapt generated code with context-aware parameter adaptation.

        Common adaptations:
        - Change language (Python -> JavaScript)
        - Change style (functional -> OOP)
        - Add/remove parameters
        - Context-aware parameter injection based on request context
        """
        # Extract patterns from fragment
        patterns = fragment.output_schema.fragment_patterns

        # Simple strategy: if output is a string (code), try to modify
        if isinstance(base_output, str):
            modified = base_output

            # Context-aware parameter injection
            # Consider both explicit parameters and context for smarter adaptation
            adapted_params = self._get_adapted_parameters(request)
            
            # Inject parameters with context awareness
            for key, value in adapted_params.items():
                if isinstance(value, str):
                    # Handle various placeholder formats
                    placeholders = [
                        f"{{{key}}}",           # {param}
                        f"${key}",              # $param
                        f":{key}:",             # :param:
                        f"<!-- {key} -->",      # HTML/XML comment style
                        f"/* {key} */",         # C-style comment
                        f"# {key}",             # Python/Ruby comment
                        f"// {key}",            # JS/Java comment
                    ]
                    
                    for placeholder in placeholders:
                        modified = modified.replace(placeholder, str(value))
                
                elif isinstance(value, (int, float, bool)):
                    # Handle numeric and boolean values
                    placeholders = [
                        f"{{{key}}}",
                        f"${key}",
                        f":{key}:",
                    ]
                    
                    for placeholder in placeholders:
                        modified = modified.replace(placeholder, str(value))

            return modified

        # Add structural adaptations for code
        if isinstance(base_output, str):
            # Check if structural adaptation is requested
            style = request.context.get("style", "").lower()
            structure = request.parameters.get("structure", "default")
            
            if style == "functional":
                modified = self._adapt_code_style_functional(base_output)
            elif style == "oop":
                modified = self._adapt_code_style_oop(base_output)
            elif style == "procedural":
                modified = self._adapt_code_style_procedural(base_output)
                
            if structure == "modular":
                modified = self._adapt_code_structure_modular(modified)

        return base_output

    async def _adapt_summary(
        self,
        base_output: any,
        fragment: SkillFragment,
        request: ExecutionRequest,
    ) -> any:
        """
        Adapt a summary with sophisticated length, tone, and focus adjustments.

        Common adaptations:
        - Change length (shorter/medium/long)
        - Change tone (formal/casual/technical/conversational)
        - Change focus (technical/business/academic/layperson)
        """
        if not isinstance(base_output, str):
            return base_output

        # Get adaptation parameters
        target_length = request.parameters.get("length", "medium")
        tone = request.parameters.get("tone", request.context.get("tone", "neutral"))
        focus = request.parameters.get("focus", request.context.get("focus", "general"))

        adapted_summary = base_output

        # Apply length adaptation
        if target_length == "short":
            # Condense to key points - first and last sentence, or first 30% whichever is shorter
            sentences = [s.strip() for s in base_output.split(".") if s.strip()]
            if len(sentences) <= 2:
                adapted_summary = base_output
            else:
                # Keep first and last sentence for very short
                if len(sentences) == 3:
                    adapted_summary = f"{sentences[0]}. {sentences[-1]}."
                else:
                    # For longer texts, take first 30% of sentences
                    split_point = max(1, int(len(sentences) * 0.3))
                    adapted_summary = ". ".join(sentences[:split_point]) + "."
                    
        elif target_length == "long":
            # Expand by adding transitional phrases and elaboration markers
            # In a real implementation, this might use LLM expansion
            # For now, we'll add connective phrases to make it flow better
            sentences = [s.strip() for s in base_output.split(".") if s.strip()]
            if len(sentences) > 1:
                elaborated = []
                for i, sentence in enumerate(sentences):
                    elaborated.append(sentence)
                    # Add transitional phrases between sentences (except last)
                    if i < len(sentences) - 1:
                        if any(word in sentence.lower() for word in ["however", "but", "although"]):
                            elaborated.append("Furthermore")
                        elif any(word in sentence.lower() for word in ["because", "since", "due to"]):
                            elaborated.append("This leads to")
                        else:
                            elaborated.append("Additionally")
                adapted_summary = ". ".join(elaborated) + "."

        # Apply tone adaptation
        adapted_summary = self._adapt_tone(adapted_summary, tone)

        # Apply focus adaptation
        adapted_summary = self._adapt_focus(adapted_summary, focus)

        return adapted_summary

    async def _adapt_translation(
        self,
        base_output: any,
        fragment: SkillFragment,
        request: ExecutionRequest,
    ) -> any:
        """
        Adapt a translation with formality, tone, and terminology adjustments.

        Common adaptations:
        - Change formality level (formal/informal)
        - Adjust tone (factual/emotional/persuasive)
        - Fix terminology (domain-specific terms)
        - Adjust dialect/regional variants
        """
        if not isinstance(base_output, str):
            return base_output

        # Get adaptation parameters
        formality = request.parameters.get("formality", request.context.get("formality", "neutral"))
        tone = request.parameters.get("tone", request.context.get("tone", "neutral"))
        dialect = request.parameters.get("dialect", request.context.get("dialect", "standard"))

        adapted_translation = base_output

        # Apply formality adaptation
        adapted_translation = self._adapt_translation_formality(adapted_translation, formality)

        # Apply tone adaptation
        adapted_translation = self._adapt_translation_tone(adapted_translation, tone)

        # Apply dialect adaptation
        adapted_translation = self._adapt_translation_dialect(adapted_translation, dialect)

        return adapted_translation

    def _adapt_translation_formality(self, text: str, formality: str) -> str:
        """Adapt translation formality level."""
        if formality not in ["formal", "informal"]:
            return text
        
        if formality == "formal":
            return self._adapt_tone(text, "formal")
        elif formality == "informal":
            return self._adapt_tone(text, "casual")
        return text

    def _adapt_translation_tone(self, text: str, tone: str) -> str:
        """Adapt translation tone."""
        if tone not in ["factual", "emotional", "persuasive"]:
            return text
        
        # Basic tone adaptations
        if tone == "factual":
            # Remove emotional language, make more objective
            emotional_words = ["amazing", "wonderful", "terrible", "horrible", "fantastic"]
            for word in emotional_words:
                text = text.replace(word, "notable")
        elif tone == "emotional":
            # Add more emotional language (basic substitution)
            factual_words = ["notable", "significant", "important"]
            for word in factual_words:
                text = text.replace(word, "remarkable")
        elif tone == "persuasive":
            # Add persuasive elements
            if not text.endswith("!"):
                text = text.rstrip(".") + "."
        
        return text

    def _adapt_translation_dialect(self, text: str, dialect: str) -> str:
        """Adapt translation to regional dialect variants."""
        # In a real implementation, this would handle regional variants
        # For now, it's a placeholder for dialect-specific adaptations
        return text

    def _adapt_code_style_functional(self, code: str) -> str:
        """Adapt code to functional programming style."""
        # Basic functional style transformations
        # In practice, this would use more sophisticated transformations
        return code

    def _adapt_code_style_oop(self, code: str) -> str:
        """Adapt code to object-oriented programming style."""
        # Basic OOP style transformations
        return code

    def _adapt_code_style_procedural(self, code: str) -> str:
        """Adapt code to procedural programming style."""
        # Basic procedural style transformations
        return code

    def _adapt_code_structure_modular(self, code: str) -> str:
        """Adapt code to modular structure."""
        # Basic modular structure transformations
        return code

    async def _complex_adapt_with_llm(
        self,
        base_output: any,
        fragment: SkillFragment,
        request: ExecutionRequest,
    ) -> any:
        """
        Use LLM for complex adaptations that simple heuristics cannot handle.
        
        This is called when adaptation complexity exceeds what rule-based
        transformations can handle.
        
        In a production system, this would:
        1. Build a prompt describing the original fragment and desired adaptation
        2. Call an LLM service
        3. Return the adapted output
        
        For now, this returns the base output with a note.
        """
        logger.info(
            "complex_adaptation_requested",
            fragment_id=fragment.fragment_id,
            task_type=request.task_type,
        )
        
        # In production, this would call the LLM service:
        # from skill_fragment_engine.services.llm_service import LLMService
        # llm = LLMService()
        # prompt = self._build_complex_adaptation_prompt(base_output, fragment, request)
        # return await llm.complete(prompt)
        
        # For now, return base output
        logger.warning("complex_adaptation_fallback_to_base", reason="LLM service not configured")
        return base_output

    def _build_complex_adaptation_prompt(
        self,
        base_output: any,
        fragment: SkillFragment,
        request: ExecutionRequest,
    ) -> str:
        """Build a prompt for complex LLM-based adaptation."""
        
        prompt = f"""You are tasked with adapting a cached fragment for a new context.

Original Fragment Purpose: {fragment.description}
Task Type: {request.task_type}

Original Output:
{base_output}

Requested Adaptation:
- Parameters: {request.parameters}
- Context: {request.context}

Please adapt the original output to fit the new context while preserving the core logic and intent.
"""
        return prompt

    def _get_adapted_parameters(self, request: ExecutionRequest) -> dict:
        """
        Get parameters adapted based on request context for smarter adaptation.
        
        This method enhances basic parameter injection by considering:
        - Context hints for parameter interpretation
        - Task-specific parameter adaptations
        - Fallback to original parameters if no context adaptation applies
        """
        # Start with original parameters
        adapted_params = dict(request.parameters)
        
        # Context-aware adaptations
        if request.context:
            # For code generation, adapt based on language/context hints
            if request.task_type == "code_generation":
                language = request.context.get("language", "").lower()
                
                # Adapt parameter naming/style based on target language
                if language in ["javascript", "typescript", "java"]:
                    # Convert snake_case to camelCase for JS/TS/Java
                    for key, value in list(adapted_params.items()):
                        if "_" in key and isinstance(value, str):
                            # Simple snake_case to camelCase conversion
                            parts = key.split("_")
                            if len(parts) > 1:
                                camel_key = parts[0] + "".join(p.capitalize() for p in parts[1:])
                                adapted_params[camel_key] = value
                                # Keep original for backward compatibility
                elif language in ["python", "ruby"]:
                    # Ensure snake_case for Python/Ruby
                    for key, value in list(adapted_params.items()):
                        if "-" in key and isinstance(value, str):
                            # Convert kebab-case to snake_case
                            snake_key = key.replace("-", "_")
                            adapted_params[snake_key] = value
                            # Keep original for backward compatibility
            
            # For text tasks, adapt based on style/formality hints
            elif request.task_type in ["text_summarization", "translation"]:
                formality = request.context.get("formality", "").lower()
                tone = request.context.get("tone", "").lower()
                
                # Add formality/tone as parameters if not already present
                if formality and "formality" not in adapted_params:
                    adapted_params["formality"] = formality
                if tone and "tone" not in adapted_params:
                    adapted_params["tone"] = tone
        
        return adapted_params

    def _generic_adapt(self, base_output: any, request: ExecutionRequest) -> any:
        """Generic adaptation fallback."""
        # Just merge request parameters into output if possible
        if isinstance(base_output, dict):
            return {**base_output, **request.parameters}
        return base_output

    def _create_variant(
        self,
        parent: SkillFragment,
        original_output: any,
        adapted_output: any,
        request: ExecutionRequest,
    ) -> Variant:
        """Create a variant record for the adaptation."""
        variant = Variant(
            variant_id=uuid4(),
            parent_fragment_id=parent.fragment_id,
            created_from="adaptation",
            diff_type="output_modification",
            before_snapshot={"result": original_output},
            after_snapshot={"result": adapted_output},
            reason=f"Adapted for new context",
            performance_delta={
                "quality_delta": 0.0,  # Would be computed from validation
            },
        )

        # Link to parent
        parent.variants.append(variant.variant_id)

        return variant

    def estimate_cost(self) -> float:
        """Estimate cost for adaptation."""
        return self.settings.adaptation_cost

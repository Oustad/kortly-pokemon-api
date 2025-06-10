"""Service for interacting with Google Gemini API for Pokemon card identification."""

import io
import logging
from typing import Any, Dict, Optional

import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError
from PIL import Image

from ..config import get_config

logger = logging.getLogger(__name__)
config = get_config()


class GeminiService:
    """Service for using Google Gemini to analyze Pokemon cards."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Gemini service with API key."""
        self._model = None
        self._api_key = api_key

    @property
    def model(self):
        """Lazy load the Gemini model."""
        if self._model is None:
            if self._api_key:
                genai.configure(api_key=self._api_key)
                logger.info("Configured Gemini with API key")
            else:
                logger.warning(
                    "No Gemini API key provided. Set GOOGLE_API_KEY environment variable."
                )
            self._model = genai.GenerativeModel(config.gemini_model)
        return self._model

    async def identify_pokemon_card(
        self,
        image_bytes: bytes,
        optimize_for_speed: bool = True,
        retry_unlimited: bool = False,
    ) -> Dict[str, Any]:
        """
        Use Gemini to identify a Pokemon card from an image.

        Args:
            image_bytes: The image data as bytes
            optimize_for_speed: If True, use optimizations to reduce processing time
            retry_unlimited: If True, retry with unlimited tokens if MAX_TOKENS error

        Returns:
            Dictionary containing Gemini's response and metadata
        """
        try:
            logger.info("🤖 Calling Gemini API for Pokemon card identification...")

            # Convert bytes to PIL Image and optimize for speed
            pil_image = Image.open(io.BytesIO(image_bytes))

            if optimize_for_speed:
                # Resize image to reduce processing time while maintaining quality
                max_dimension = min(800, config.image_max_dimension)  # Use smaller of the two for speed
                if max(pil_image.size) > max_dimension:
                    ratio = max_dimension / max(pil_image.size)
                    new_size = tuple(int(dim * ratio) for dim in pil_image.size)
                    pil_image = pil_image.resize(new_size, Image.Resampling.LANCZOS)
                    logger.info(f"Resized image to {new_size} for faster processing")

            # Optimized prompt with structured TCG search format
            prompt = """Identify this Pokemon card and provide TCG search parameters.

Format your response exactly like this:
TCG_SEARCH_START
{
  "name": "exact pokemon name",
  "set_name": "set name if visible", 
  "number": "card number if visible",
  "hp": "HP value if visible",
  "types": ["Pokemon type like Fire, Water etc"]
}
TCG_SEARCH_END

Then provide brief analysis:
1. Card identification
2. Key features
3. Estimated value
4. Condition"""

            # Configure generation settings
            if retry_unlimited:
                # No token limit on retry
                generation_config = genai.types.GenerationConfig(
                    temperature=config.gemini_temperature,
                )
            else:
                generation_config = genai.types.GenerationConfig(
                    max_output_tokens=config.gemini_max_tokens,
                    temperature=config.gemini_temperature,
                )

            # Configure permissive safety settings for trading card analysis
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE",
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE",
                },
            ]

            response = self.model.generate_content(
                [prompt, pil_image],
                generation_config=generation_config,
                safety_settings=safety_settings,
            )

            # Extract the text response with proper error handling
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                finish_reason = (
                    candidate.finish_reason.name if candidate.finish_reason else "UNKNOWN"
                )

                # Check if response was blocked by safety filters
                if finish_reason == "SAFETY":
                    safety_issues = []
                    if candidate.safety_ratings:
                        for rating in candidate.safety_ratings:
                            if rating.probability.name in ["MEDIUM", "HIGH"]:
                                safety_issues.append(
                                    f"{rating.category.name}: {rating.probability.name}"
                                )

                    logger.warning(
                        f"⚠️ Gemini response blocked by safety filters: {safety_issues}"
                    )
                    return {
                        "success": False,
                        "error": f"Response blocked by safety filters: {', '.join(safety_issues)}",
                        "finish_reason": finish_reason,
                    }

                # Check if we have valid content
                if (
                    hasattr(candidate, "content")
                    and candidate.content
                    and candidate.content.parts
                ):
                    response_text = "".join(
                        [
                            part.text
                            for part in candidate.content.parts
                            if hasattr(part, "text")
                        ]
                    )

                    if response_text:
                        # Handle MAX_TOKENS as a successful partial response
                        is_truncated = finish_reason == "MAX_TOKENS"
                        if is_truncated:
                            response_text += "\n\n[Response truncated due to length limit]"
                            logger.warning(
                                f"⚠️ Gemini response truncated ({len(response_text)} chars)"
                            )

                        result = {
                            "success": True,
                            "response": response_text,
                            "prompt_tokens": (
                                response.usage_metadata.prompt_token_count
                                if hasattr(response, "usage_metadata")
                                else None
                            ),
                            "response_tokens": (
                                response.usage_metadata.candidates_token_count
                                if hasattr(response, "usage_metadata")
                                else None
                            ),
                            "finish_reason": finish_reason,
                            "truncated": is_truncated,
                        }

                        logger.info(
                            f"✅ Gemini response received ({len(response_text)} characters)"
                        )
                        return result

                logger.warning(
                    f"⚠️ Gemini returned no valid content. Finish reason: {finish_reason}"
                )
                return {
                    "success": False,
                    "error": f"No valid content returned. Finish reason: {finish_reason}",
                    "finish_reason": finish_reason,
                }
            else:
                logger.warning("⚠️ Gemini returned no candidates")
                return {
                    "success": False,
                    "error": "No candidates returned from Gemini",
                }

        except GoogleAPIError as e:
            logger.error(f"❌ Gemini API error: {str(e)}")
            return {
                "success": False,
                "error": f"Gemini API error: {str(e)}",
            }
        except Exception as e:
            logger.error(f"❌ Unexpected error calling Gemini: {str(e)}")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
            }

    def count_tokens(self, text: str) -> int:
        """Count tokens in a text string."""
        try:
            return self.model.count_tokens(text).total_tokens
        except Exception as e:
            logger.warning(f"Failed to count tokens: {e}")
            return 0
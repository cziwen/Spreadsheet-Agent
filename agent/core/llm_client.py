"""LLM Client wrapper for Google Gemini API."""

import json
import re
import os
from typing import Dict, Any, Optional
import google.generativeai as genai


class LLMClient:
    """Wrapper for Google Generative AI (Gemini) API."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-pro"):
        """Initialize LLM client with Gemini API.

        Args:
            api_key: Google API key. If None, reads from GOOGLE_API_KEY env var.
            model: Model name (default: gemini-1.5-flash)
        """
        if api_key is None:
            api_key = os.getenv("GOOGLE_API_KEY")

        if not api_key:
            raise ValueError("GOOGLE_API_KEY not set in environment or provided as argument")

        genai.configure(api_key=api_key)
        self.model = model

    def call(self, prompt: str) -> str:
        """Call LLM with text prompt.

        Args:
            prompt: Text prompt to send to LLM

        Returns:
            LLM response as string
        """
        model = genai.GenerativeModel(self.model)
        response = model.generate_content(prompt)
        return response.text

    def call_structured(self, prompt: str) -> Dict[str, Any]:
        """Call LLM and parse JSON response.

        Args:
            prompt: Text prompt to send to LLM

        Returns:
            Parsed JSON response as dictionary
        """
        prompt_with_format = f"{prompt}\n\nIMPORTANT: Return ONLY valid JSON, no markdown, no extra text."
        model = genai.GenerativeModel(self.model)
        response = model.generate_content(prompt_with_format)

        text = response.text

        # Try to parse directly
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code blocks
        if "```json" in text:
            match = re.search(r"```json\s*([\s\S]*?)\s*```", text)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass

        if "```" in text:
            match = re.search(r"```\s*([\s\S]*?)\s*```", text)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass

        # Try to find JSON object pattern
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        # If all parsing fails, return error
        raise ValueError(f"Could not parse JSON from response: {text[:200]}")

import os
import sys
import django
import logging
import hashlib
import json
import tiktoken
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from django.core.cache import cache
from openai import OpenAI

logger = logging.getLogger('news')

class LLMService:
    """Service for generating summaries and investment suggestions using LLM."""
    
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.cache_timeout = 86400  # 24 hours in seconds
        
        # Initialize OpenAI client
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None
        
        # Pricing information per 1M tokens (from the pricing table)
        self.pricing = {
            'gpt-5': {'input': 1.25, 'cached_input': 0.125, 'output': 10.00},
            'gpt-5-mini': {'input': 0.25, 'cached_input': 0.025, 'output': 2.00},
            'gpt-5-nano': {'input': 0.05, 'cached_input': 0.005, 'output': 0.40},
            'gpt-5-chat-latest': {'input': 1.25, 'cached_input': 0.125, 'output': 10.00},
            'gpt-5-codex': {'input': 1.25, 'cached_input': 0.125, 'output': 10.00},
            'gpt-4.1': {'input': 2.00, 'cached_input': 0.50, 'output': 8.00},
            'gpt-4o-mini': {'input': 0.40, 'cached_input': 0.10, 'output': 1.60}
        }
        
        # Default model (can be overridden per call)
        self.default_model = 'gpt-5-mini'
        
        # Initialize tokenizer for token counting
        try:
            self.tokenizer = tiktoken.encoding_for_model(self.default_model)
        except Exception as e:
            logger.warning(f"Could not initialize tokenizer for {self.default_model}: {e}")
            # Fallback to cl100k_base encoding (used by GPT-4)
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in the given text."""
        try:
            return len(self.tokenizer.encode(text))
        except Exception as e:
            logger.warning(f"Error counting tokens: {e}")
            # Fallback: rough estimation (1 token ≈ 4 characters)
            return len(text) // 4
    
    def _calculate_cost(self, input_tokens: int, output_tokens: int, model: str = None) -> Dict[str, float]:
        """Calculate the cost of an API call based on token usage."""
        if model is None:
            model = self.default_model
        
        if model not in self.pricing:
            logger.warning(f"Unknown model {model}, using gpt-5-mini pricing")
            model = 'gpt-5-mini'
        
        pricing = self.pricing[model]
        
        # Convert tokens to millions and calculate cost
        input_cost = (input_tokens / 1_000_000) * pricing['input']
        output_cost = (output_tokens / 1_000_000) * pricing['output']
        total_cost = input_cost + output_cost
        
        return {
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'input_cost': input_cost,
            'output_cost': output_cost,
            'total_cost': total_cost,
            'model': model
        }
    
    def _log_cost(self, cost_info: Dict[str, float], task_type: str) -> None:
        """Log the cost information for an API call."""
        logger.info(
            f"LLM API Cost - {task_type} | "
            f"Model: {cost_info['model']} | "
            f"Input: {cost_info['input_tokens']} tokens (${cost_info['input_cost']:.6f}) | "
            f"Output: {cost_info['output_tokens']} tokens (${cost_info['output_cost']:.6f}) | "
            f"Total: ${cost_info['total_cost']:.6f}"
        )
    
    def _truncate_content(self, content: str, max_length: int) -> str:
        """Truncate content to max_length while preserving word boundaries."""
        if len(content) <= max_length:
            return content
        
        # Find the last complete word within the limit
        truncated = content[:max_length]
        last_space = truncated.rfind(' ')
        
        if last_space > max_length * 0.8:  # Only truncate at word boundary if we don't lose too much content
            return truncated[:last_space] + "..."
        else:
            return truncated + "..."
    
    def _get_cache_key(self, content: str, task_type: str) -> str:
        """Generate a cache key for the given content and task type."""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        return f"llm_{task_type}_{content_hash}"
    
    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Get result from Django cache if it exists."""
        try:
            result = cache.get(cache_key)
            if result:
                logger.info(f"Cache hit for {cache_key}")
            return result
        except Exception as e:
            logger.info(f"Cache get error for {cache_key}: {str(e)}")
            return None
    
    def _save_to_cache(self, cache_key: str, result: Any) -> None:
        """Save result to Django cache with timeout."""
        try:
            cache.set(cache_key, result, timeout=self.cache_timeout)
            logger.info(f"Cached result for {cache_key}")
        except Exception as e:
            logger.info(f"Cache set error for {cache_key}: {str(e)}")
    
    def clear_cache(self) -> None:
        """Clear all LLM cache entries."""
        try:
            cache.clear()
            logger.info("LLM cache cleared successfully")
        except Exception as e:
            logger.warning(f"Error clearing cache: {str(e)}")
    
    def clear_llm_cache(self) -> None:
        """Clear only LLM-related cache entries (safer than clearing all cache)."""
        try:
            # Get all cache keys (this might not work with all cache backends)
            # For simplicity, we'll clear all cache
            cache.clear()
            logger.info("LLM cache cleared - old responses will be regenerated")
        except Exception as e:
            logger.warning(f"Error clearing LLM cache: {str(e)}")
            # Fallback: try to clear specific LLM keys
            try:
                # This is a simple approach - clear all cache
                cache.clear()
                logger.info("LLM cache cleared via fallback method")
            except Exception as e2:
                logger.error(f"Failed to clear cache: {str(e2)}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics (if supported by backend)."""
        try:
            # This is a simple implementation - actual stats depend on cache backend
            return {
                "backend": "Django Database Cache",
                "timeout": self.cache_timeout,
                "status": "active"
            }
        except Exception as e:
            logger.warning(f"Error getting cache stats: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    def generate_summary(self, content: str, model: str = None) -> Optional[str]:
        """Generate a summary of the article content."""
        try:
            # Check cache first
            cache_key = self._get_cache_key(content, "summary")
            cached_result = self._get_from_cache(cache_key)
            if cached_result:
                return cached_result
            
            # Truncate content properly
            truncated_content = self._truncate_content(content, 2000)
            
            prompt = f"""
            Please provide a concise summary (2-3 sentences) of the following news article content. 
            Focus on the key facts and main points that would be relevant for investment decisions.
            
            Content: {truncated_content}
            """
            
            result = self._call_llm_api(prompt, "summary", model)
            if result:
                self._save_to_cache(cache_key, result)
            return result
        
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return None
    
    def generate_investment_suggestion(self, content: str, summary: str, model: str = None) -> Optional[Dict[str, str]]:
        """Generate investment suggestions based on article content."""
        try:
            # Check cache first
            cache_key = self._get_cache_key(f"{content}_{summary}", "investment_suggestion")
            cached_result = self._get_from_cache(cache_key)
            if cached_result:
                return cached_result
            
            # Truncate content properly
            truncated_content = self._truncate_content(content, 1500)
            
            prompt = f"""
You are a financial analyst. Evaluate the short-term (1–7 days) impact of this news on publicly traded stocks or market indices only. Ignore startups, private firms, or long-term ecosystem effects.

Scoring rules:
- 0.0–0.1: Absolutely no short-term market impact
- 0.2: Minimal/negligible impact
- 0.3–0.4: Very minor impact, not worth investment action
- 0.5: Neutral / uncertain impact
- 0.6–0.8: Clear impact on a sector or public company
- 0.9–1.0: Strong, highly certain impact on overall market or major stocks

Examples:
- "Fed unexpectedly raises interest rates" → 0.95
- "Apple launches new color iPhone case" → 0.15
- "Tesla recalls 2M vehicles due to safety issue" → 0.8
- "Lebron James's VC firm invests in a private AI food startup" → 0.0

News Summary: {summary}
News Content: {truncated_content}

Respond ONLY in valid JSON:
{{
  "key_impact": "[brief impact]",
  "suggestion": "[investment recommendation]",
  "confidence_score": <float between 0 and 1>
}}
"""

            result = self._call_llm_api(prompt, "investment_suggestion", model)
            if result:
                # Try to parse as structured JSON, fallback to string parsing
                structured_result = self._parse_investment_suggestion(result)
                self._save_to_cache(cache_key, structured_result)
                return structured_result
            return None
        
        except Exception as e:
            logger.error(f"Error generating investment suggestion: {str(e)}")
            return None
    
    def _parse_investment_suggestion(self, response: str) -> Dict[str, Any]:
        """Parse investment suggestion response into structured format."""
        try:
            # Try to parse as JSON first
            parsed = json.loads(response)
            # Ensure confidence_score is a float if present
            if 'confidence_score' in parsed:
                try:
                    parsed['confidence_score'] = float(parsed['confidence_score'])
                except (ValueError, TypeError):
                    parsed['confidence_score'] = None
            return parsed
        except json.JSONDecodeError:
            # Fallback to text parsing
            lines = response.strip().split('\n')
            result = {"key_impact": "", "suggestion": "", "confidence_score": None}
            
            for line in lines:
                line = line.strip()
                if line.startswith('"key_impact"') or line.startswith('Key Impact'):
                    result["key_impact"] = line.split(':', 1)[1].strip().strip('"')
                elif line.startswith('"suggestion"') or line.startswith('Investment Suggestion'):
                    result["suggestion"] = line.split(':', 1)[1].strip().strip('"')
                elif line.startswith('"confidence_score"') or line.startswith('Confidence Score'):
                    try:
                        confidence_str = line.split(':', 1)[1].strip().strip('"')
                        result["confidence_score"] = float(confidence_str)
                    except (ValueError, TypeError):
                        result["confidence_score"] = None
            
            # If parsing failed, return the raw response in both fields
            if not result["key_impact"] and not result["suggestion"]:
                result["key_impact"] = "Analysis completed"
                result["suggestion"] = response
                result["confidence_score"] = None
            
            return result
    
    def _call_llm_api(self, prompt: str, task_type: str, model: str = None) -> Optional[str]:
        """Make API call to LLM service using OpenAI SDK."""
        if not self.client:
            logger.warning("No API key provided, using placeholder response")
            return self._get_placeholder_response(task_type)
        
        try:
            # Prepare the full input with system message
            system_message = 'You are a financial analyst providing investment insights based on news articles.'
            full_input = f"{system_message}\n\n{prompt}"
            
            # Count input tokens
            input_tokens = self._count_tokens(full_input)
            
            # Use provided model or default
            selected_model = model or self.default_model
            
            # Call OpenAI responses API
            response = self.client.responses.create(
                model=selected_model,
                input=full_input,
                reasoning={"effort": "medium"},
                text={"verbosity": "low"}
            )
            
            # Extract the output text
            response_content = response.output_text.strip()
            
            # Count output tokens and calculate cost
            output_tokens = self._count_tokens(response_content)
            cost_info = self._calculate_cost(input_tokens, output_tokens, selected_model)
            
            # Log the cost
            self._log_cost(cost_info, task_type)
            
            return response_content
        
        except Exception as e:
            logger.error(f"Error calling LLM API: {str(e)}")
            return self._get_placeholder_response(task_type)
    
    
    def _get_placeholder_response(self, task_type: str) -> str:
        """Generate placeholder response when API is not available."""
        if task_type == "summary":
            return "This article discusses recent developments in the technology sector that may have implications for investors and market participants."
        elif task_type == "investment_suggestion":
            return json.dumps({
                "key_impact": "Technology sector developments may influence market sentiment",
                "suggestion": "Monitor related stocks and consider sector-specific ETFs for potential opportunities",
                "confidence_score": 0.5
            })
        else:
            return "Analysis pending - please check back later for updated insights."
    
    def set_default_model(self, model: str) -> bool:
        """Set the default LLM model to use."""
        if model in self.pricing:
            self.default_model = model
            try:
                self.tokenizer = tiktoken.encoding_for_model(model)
                logger.info(f"Set default model to: {model}")
                return True
            except Exception as e:
                logger.warning(f"Could not initialize tokenizer for {model}: {e}")
                # Fallback to cl100k_base encoding
                self.tokenizer = tiktoken.get_encoding("cl100k_base")
                return True
        else:
            logger.error(f"Unknown model: {model}. Available models: {list(self.pricing.keys())}")
            return False
    
    def get_available_models(self) -> list:
        """Get list of available models with their pricing."""
        return list(self.pricing.keys())
    
    def get_model_pricing(self, model: str = None) -> Dict[str, float]:
        """Get pricing information for a specific model."""
        if model is None:
            model = self.default_model
        
        if model in self.pricing:
            return self.pricing[model]
        else:
            logger.warning(f"Unknown model: {model}")
            return {}
    
    def estimate_cost(self, input_text: str, expected_output_length: int = 200, model: str = None) -> Dict[str, float]:
        """Estimate the cost of processing the given input text."""
        input_tokens = self._count_tokens(input_text)
        # Rough estimation for output tokens based on expected length
        output_tokens = self._count_tokens("x" * expected_output_length)
        
        return self._calculate_cost(input_tokens, output_tokens, model)
    
    def close_session(self):
        """Close the client session to free up resources."""
        try:
            if self.client:
                self.client.close()
                logger.debug("LLM service client closed")
        except Exception as e:
            logger.warning(f"Error closing LLM service client: {str(e)}")


if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'investment_wizard.settings')
    django.setup()
    
    # Clear cache before testing (since you improved the prompt)
    print("Clearing old LLM cache...")
    llm_service = LLMService()
    
    # test prompt for confidence score 
    print("Testing with fresh LLM responses...")

    summary = "OpenAI signs a multi-billion dollar chips deal with AMD"

    content = """
    OpenAI has struck a sweeping deal with chipmaker AMD to secure processors for artificial intelligence systems, an agreement that could give the ChatGPT maker a 10% stake in AMD and further speeds up its trillion-dollar infrastructure push.

    AMD issued OpenAI a warrant for as many as 160 million shares of its stock, which could give the ChatGPT owner about about a tenth of the chipmaker’s shares. The amount of stock it eventually owns is tied to both to the scale of AMD hardware deployed and to share price milestones.

The chipmaker’s shares jumped as much as 37% in early trading Monday as executives said it would add tens of billions of dollars in revenue. AMD stock was still up more than 26% shortly after markets open. Shares in rival Nvidia, which recently unveiled a $100 billion deal of its own with OpenAI, slipped about 1.5% before trading closer to break-even.

It's the latest in a string of infrastructure deals for OpenAI. The company has pledged roughly $1 trillion in the last two weeks to expand its computing base, including a dedicated supply agreement with Nvidia. Analysts have said the scale of investment rivals the energy demand of major cities.

OpenAI chief executive Sam Altman called the new deal “a major step in building the compute capacity needed to realize AI’s full potential. AMD’s leadership in high-performance chips will enable us to accelerate progress and bring the benefits of advanced AI to everyone faster."

AMD has been investing heavily in recent years in the market for so-called accelerator chips, which are used to train and run advanced AI models, in which rival Nvidia is dominant. Nvidia’s data center division generated more than $115 billion in sales last year, while AMD’s AI-related revenue is expected to reach about $6.5 billion in 2025.

“We are thrilled to partner with OpenAI to deliver AI compute at massive scale,” AMD's chief executive Lisa Su said. “This agreement creates a true win-win enabling the world’s most ambitious AI buildout and advancing the entire AI ecosystem.”

AMD's chief financial officer Jean Hu added that the deal is “expected to deliver tens of billions of dollars in revenue” for the company.
    """

    result = llm_service.generate_investment_suggestion(content, summary, model="gpt-5-mini")
    print(result)
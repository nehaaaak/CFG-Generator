from google import genai 
from google.genai import types
import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if not GEMINI_API_KEY:
    print("GEMINI_API_KEY not configured. AI features disabled.")
    client = None
else:
    client = genai.Client(api_key=GEMINI_API_KEY)


def generate_completion(
    prompt: str,
    max_tokens: int = 300,
    temperature: float = 0.3,
    thinking_budget: int = 0
) -> dict:
    if not client:
        return {
            "text": "AI features unavailable - API key not configured",
            "tokens_used": 0,
            "error": "No API key"
        }
    
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
                thinking_config=types.ThinkingConfig(
                    thinking_budget=thinking_budget
                )
            ),
        )

        print("DEBUG raw response:", response)

        # Truncation guard
        candidate = response.candidates[0]
        if candidate.finish_reason.name == "MAX_TOKENS":
            print(f"WARNING: Response was truncated at max_tokens limit ({max_tokens})")
        
        tokens_used = 0
        try:
            if hasattr(response, 'usage_metadata'):
                tokens_used = (
                    response.usage_metadata.prompt_token_count +
                    response.usage_metadata.candidates_token_count
                )
        except:
            tokens_used = response.usage_metadata.total_token_count

        text = ""
        if hasattr(response, "text") and response.text:
            text = response.text.strip()
        elif response.candidates:
            # text = response.candidates[0].content.parts[0].text.strip()
            parts = response.candidates[0].content.parts
            text = "".join(
                part.text for part in parts if hasattr(part, "text") and part.text
            ).strip()

        if not text or len(text) < 10:
            return {
                "text": "",
                "tokens_used": tokens_used,
                "error": "Empty or incomplete response from AI"
            }
        
        return {
            "text": text,
            "tokens_used": tokens_used,
            "error": None
        }
    
    except Exception as e:
        return {
            "text": f"Error: {str(e)}",
            "tokens_used": 0,
            "error": str(e)
        }


def is_available() -> bool:
    """Check if AI service is available"""
    return client is not None
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if not GEMINI_API_KEY:
    print("GEMINI_API_KEY not configured. AI features disabled.")
    model = None
else:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)


def generate_completion(
    prompt: str,
    max_tokens: int = 180,
    temperature: float = 0.3
) -> dict:
    """
    Generate completion from Gemini.
    
    Returns:
        {
            "text": str,
            "tokens_used": int,
            "error": str | None
        }
    """
    if not model:
        return {
            "text": "AI features unavailable - API key not configured",
            "tokens_used": 0,
            "error": "No API key"
        }
    
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            ),
            request_options={"timeout": 20}
        )
        
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
            text = response.candidates[0].content.parts[0].text.strip()
        
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
    return model is not None
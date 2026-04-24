from google import genai 
from google.genai import types
import os
import time
from dotenv import load_dotenv


load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_API_KEY_BACKUP = os.getenv("GEMINI_API_KEY_BACKUP")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if not GEMINI_API_KEY:
    print("GEMINI_API_KEY not configured. AI features disabled.")
    primary_client = None
else:
    primary_client = genai.Client(api_key=GEMINI_API_KEY)

if not GEMINI_API_KEY_BACKUP:
    print("GEMINI_API_KEY not configured. AI features disabled.")
    backup_client = None
else:
    backup_client = genai.Client(api_key=GEMINI_API_KEY_BACKUP)


def generate_completion(
    prompt: str,
    max_tokens: int = 300,
    temperature: float = 0.3,
    thinking_budget: int = 0
) -> dict:
    if not primary_client:
        return {
            "text": "AI features unavailable - API key not configured",
            "tokens_used": 0,
            "error": "No API key"
        }
    
    MAX_RETRIES = 1   
    BASE_DELAY = 1.5

    clients = [primary_client, backup_client]
    last_error = None

    for client_idx, active_client in enumerate(clients):
        if not active_client:
            continue
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = active_client.models.generate_content(
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

                print(f"DEBUG: success using {'primary' if client_idx==0 else 'backup'} key")
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
                    # tokens_used = response.usage_metadata.total_token_count
                    tokens_used = getattr(response.usage_metadata, "total_token_count", 0)

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
                error_msg = str(e)
                last_error = error_msg

                # if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                #     return {
                #         "text": "",
                #         "tokens_used": 0,
                #         "error": "Quota exceeded. Try later."
                #     }

                if "503" in error_msg or "UNAVAILABLE" in error_msg:
                    if attempt < MAX_RETRIES:
                        delay = BASE_DELAY * (2 ** attempt)
                        print(f"DEBUG: Retry {attempt+1} after {delay}s due to 503...")
                        time.sleep(delay)
                        continue

                # switch to backup key on 503 / 429
                if ("503" in error_msg or "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg):
                    print("Switching to backup key...")
                    break  # go to next client

                return {
                    "text": "",
                    "tokens_used": 0,
                    "error": error_msg
                }
        
    return {
        "text": "",
        "tokens_used": 0,
        "error": last_error or "All keys failed"
    }


def is_available() -> bool:
    """Check if AI service is available"""
    return primary_client is not None or backup_client is not None
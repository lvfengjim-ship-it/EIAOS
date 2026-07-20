import os
import httpx
from typing import List, Dict, Any, Optional

class OllamaClient:
    """支持多模型的 Ollama 客户端"""

    MODELS = {
        "gemma4": "gemma4:31b",
        "qwen": "qwen3.6:27b",
        "coder": "qwen3-coder:30b",
        "fast": "nemotron-3-nano:30b",
        "default": "gemma4:31b"
    }

    def __init__(self, model_key: Optional[str] = None):
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model_key = model_key or "default"
        self.model = self.MODELS.get(self.model_key, self.MODELS["default"])
        self.client = httpx.AsyncClient(timeout=300.0)

    async def chat(self, messages: List[Dict[str, str]], 
                   temperature: float = 0.3,
                   model_override: Optional[str] = None) -> Dict[str, Any]:
        model = self.MODELS.get(model_override, self.model)

        try:
            if "gemma" in model:
                prompt = self._build_gemma_prompt(messages)
            elif "qwen" in model:
                prompt = self._build_qwen_prompt(messages)
            else:
                prompt = self._build_default_prompt(messages)

            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_ctx": 32768,
                        "num_predict": 8000,
                        "top_p": 0.9,
                        "repeat_penalty": 1.1,
                    }
                }
            )
            data = response.json()

            return {
                "content": data.get("response", ""),
                "model": model,
                "eval_duration": data.get("eval_duration"),
            }

        except Exception as e:
            return {"error": str(e), "content": None}

    def _build_gemma_prompt(self, messages: List[Dict]) -> str:
        prompt = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                continue
            gemma_role = "model" if role == "assistant" else "user"
            prompt += f"<start_of_turn>{gemma_role}\n{content}<end_of_turn>\n"
        prompt += "<start_of_turn>model\n"
        return prompt

    def _build_qwen_prompt(self, messages: List[Dict]) -> str:
        prompt = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt += f"<|im_start|>{role}\n{content}\n<|im_end|>\n"
        prompt += "<|im_start|>assistant\n"
        return prompt

    def _build_default_prompt(self, messages: List[Dict]) -> str:
        prompt = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt += f"{role}: {content}\n\n"
        prompt += "assistant: "
        return prompt

    async def close(self):
        await self.client.aclose()

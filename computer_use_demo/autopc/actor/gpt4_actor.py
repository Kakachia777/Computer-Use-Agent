from typing import List, Dict, Any, Optional, Callable
import openai
from anthropic.types import APIResponse
from anthropic.types.beta import BetaMessage, BetaMessageParam, BetaContentBlock

class GPT4Actor:
    """GPT-4o implementation for computer control."""
    
    def __init__(
        self,
        api_key: str,
        system_prompt_suffix: str = "",
        api_response_callback: Optional[Callable[[APIResponse[BetaMessage]], None]] = None,
        max_tokens: int = 4096,
        only_n_most_recent_images: Optional[int] = None,
        selected_screen: int = 0
    ):
        self.client = openai.Client(api_key=api_key)
        self.system_prompt = f"""You are a computer control assistant. Help users control their computer through natural language.
        Translate user requests into specific actions. {system_prompt_suffix}"""
        self.api_response_callback = api_response_callback
        self.max_tokens = max_tokens
        self.only_n_most_recent_images = only_n_most_recent_images
        self.selected_screen = selected_screen

    async def __call__(
        self,
        messages: List[BetaMessageParam],
        tool_results: Optional[List[Dict]] = None
    ) -> BetaMessage:
        try:
            formatted_messages = self._format_messages(messages, tool_results)
            
            response = await self.client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=formatted_messages,
                max_tokens=self.max_tokens,
                temperature=0.7
            )
            
            converted_response = self._convert_to_anthropic_format(response)
            
            if self.api_response_callback:
                self.api_response_callback(converted_response)
                
            return converted_response
            
        except Exception as e:
            raise Exception(f"GPT-4o processing failed: {str(e)}")

    def _format_messages(
        self,
        messages: List[BetaMessageParam],
        tool_results: Optional[List[Dict]] = None
    ) -> List[Dict]:
        formatted = [{"role": "system", "content": self.system_prompt}]
        
        for msg in messages:
            content = []
            if isinstance(msg.get("content"), list):
                for block in msg["content"]:
                    if block["type"] == "text":
                        content.append({
                            "type": "text",
                            "text": block["text"]
                        })
                    elif block["type"] == "image":
                        content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{block['image_url']}"
                            }
                        })
            else:
                content = msg.get("content", "")
                
            formatted.append({
                "role": msg["role"],
                "content": content
            })
            
        if tool_results:
            formatted.append({
                "role": "assistant",
                "content": f"Previous tool results: {str(tool_results)}"
            })
            
        return formatted

    def _convert_to_anthropic_format(self, response) -> BetaMessage:
        """Convert OpenAI response to Anthropic format for compatibility."""
        content = response.choices[0].message.content
        if isinstance(content, list):
            # Handle potential multi-modal responses
            text_content = " ".join(
                block["text"] for block in content 
                if block["type"] == "text"
            )
        else:
            text_content = content
            
        return BetaMessage(
            id="msg_" + response.id,
            type="message",
            role="assistant",
            content=text_content,
            model="gpt4o",
            stop_reason="end_turn",
            usage={
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens
            }
        )

    def to_params(self) -> Dict[str, Any]:
        """Return parameters for tool configuration."""
        return {
            "name": "gpt4o",
            "description": "GPT-4o Vision model for computer control",
            "parameters": {
                "type": "object",
                "properties": {
                    "api_key": {
                        "type": "string",
                        "description": "OpenAI API key"
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum tokens for response"
                    }
                },
                "required": ["api_key"]
            }
        } 
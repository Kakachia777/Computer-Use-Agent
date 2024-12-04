"""
Agentic sampling loop that calls the Anthropic API and local implenmentation of anthropic-defined computer use tools.
"""
import asyncio
import platform
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from typing import Any, cast

from anthropic import Anthropic, AnthropicBedrock, AnthropicVertex, APIResponse
from anthropic.types import (
    ToolResultBlockParam,
)
from anthropic.types.beta import (
    BetaContentBlock,
    BetaContentBlockParam,
    BetaImageBlockParam,
    BetaMessage,
    BetaMessageParam,
    BetaTextBlockParam,
    BetaToolResultBlockParam,
)
from anthropic.types import TextBlock
from anthropic.types.beta import BetaMessage, BetaTextBlock, BetaToolUseBlock

from .tools import BashTool, ComputerTool, EditTool, ToolCollection, ToolResult

from PIL import Image
from io import BytesIO
import gradio as gr
from typing import Dict

from computer_use_demo.autopc.actor.anthropic_actor import AnthropicActor
from computer_use_demo.autopc.executor.anthropic_executor import AnthropicExecutor

from computer_use_demo.autopc.actor.gpt4_actor import GPT4Actor
from computer_use_demo.autopc.actor.base import APIProvider


BETA_FLAG = "computer-use-2024-10-22"


class APIProvider(StrEnum):
    ANTHROPIC = "anthropic"
    BEDROCK = "bedrock"
    VERTEX = "vertex"


PROVIDER_TO_DEFAULT_MODEL_NAME: dict[APIProvider, str] = {
    APIProvider.ANTHROPIC: "claude-3-5-sonnet-20241022",
    APIProvider.BEDROCK: "anthropic.claude-3-5-sonnet-20241022-v2:0",
    APIProvider.VERTEX: "claude-3-5-sonnet-v2@20241022",
}


# This system prompt is optimized for the Docker environment in this repository and
# specific tool combinations enabled.
# We encourage modifying this system prompt to ensure the model has context for the
# environment it is running in, and to provide any additional information that may be
# helpful for the task at hand.
SYSTEM_PROMPT = f"""<SYSTEM_CAPABILITY>
* You are utilizing a Windows system with internet access.
* The current date is {datetime.today().strftime('%A, %B %d, %Y')}.
</SYSTEM_CAPABILITY>
"""

import base64
from PIL import Image
from io import BytesIO
def decode_base64_image_and_save(base64_str):
    # 移除base64字符串的前缀（如果存在）
    if base64_str.startswith("data:image"):
        base64_str = base64_str.split(",")[1]
    # 解码base64字符串并将其转换为PIL图像
    image_data = base64.b64decode(base64_str)
    image = Image.open(BytesIO(image_data))
    # 保存图像为screenshot.png
    import datetime
    image.save(f"{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.png")
    print("screenshot saved")
    return f"{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.png"

def decode_base64_image(base64_str):
    # 移除base64字符串的前缀（如果存在）
    if base64_str.startswith("data:image"):
        base64_str = base64_str.split(",")[1]
    # 解码base64字符串并将其转换为PIL图像
    image_data = base64.b64decode(base64_str)
    image = Image.open(BytesIO(image_data))
    return image


async def sampling_loop(
    *,
    model: str,
    provider: APIProvider,
    system_prompt_suffix: str,
    messages: list[BetaMessageParam],
    output_callback: Callable[[BetaContentBlock], None],
    tool_output_callback: Callable[[ToolResult, str], None],
    api_response_callback: Callable[[APIResponse[BetaMessage]], None],
    api_key: str,
    only_n_most_recent_images: int | None = None,
    max_tokens: int = 4096,
):
    """
    Agentic sampling loop for the assistant/tool interaction of computer use.
    """
    tool_collection = ToolCollection(
        ComputerTool(),
        BashTool(),
        EditTool(),
    )
    system = (
        f"{SYSTEM_PROMPT}{' ' + system_prompt_suffix if system_prompt_suffix else ''}"
    )

    while True:
        # Action Generation
        if only_n_most_recent_images:
            _maybe_filter_to_n_most_recent_images(messages, only_n_most_recent_images)

        if provider == APIProvider.ANTHROPIC:
            client = Anthropic(api_key=api_key)
        elif provider == APIProvider.VERTEX:
            client = AnthropicVertex()
        elif provider == APIProvider.BEDROCK:
            client = AnthropicBedrock()

        # Call the API
        # we use raw_response to provide debug information to streamlit. Your
        # implementation may be able call the SDK directly with:
        # `response = client.messages.create(...)` instead.
        print(messages)
        raw_response = client.beta.messages.with_raw_response.create(
            max_tokens=max_tokens,
            messages=messages,
            model=model,
            system=system,
            tools=tool_collection.to_params(),
            betas=["computer-use-2024-10-22"],
            temperature=0.0,
        )

        api_response_callback(cast(APIResponse[BetaMessage], raw_response))

        response = raw_response.parse()

        messages.append(
            {
                "role": "assistant",
                "content": cast(list[BetaContentBlockParam], response.content),
            }
        )

        tool_result_content: list[BetaToolResultBlockParam] = []
        for content_block in cast(list[BetaContentBlock], response.content):
            output_callback(content_block)
            if content_block.type == "tool_use":
                result = await tool_collection.run(
                    name=content_block.name,
                    tool_input=cast(dict[str, Any], content_block.input),
                )
                tool_result_content.append(
                    _make_api_tool_result(result, content_block.id)
                )
                tool_output_callback(result, content_block.id)

        if not tool_result_content:
            return messages

        messages.append({"content": tool_result_content, "role": "user"})


def sampling_loop_sync(
    *,
    model: str,
    provider: APIProvider,
    system_prompt_suffix: str,
    messages: list[BetaMessageParam],
    output_callback: Callable[[BetaContentBlock], None],
    tool_output_callback: Callable[[ToolResult, str], None],
    api_response_callback: Callable[[APIResponse[BetaMessage]], None],
    api_key: str,
    only_n_most_recent_images: int | None = None,
    max_tokens: int = 4096,
    selected_screen: int = 0
):
    """Synchronous agentic sampling loop for the assistant/tool interaction."""
    
    # Create appropriate actor based on provider
    if provider == APIProvider.ANTHROPIC:
        actor = AnthropicActor(
            model=model,
            provider=provider,
            system_prompt_suffix=system_prompt_suffix,
            api_key=api_key,
            api_response_callback=api_response_callback,
            max_tokens=max_tokens,
            only_n_most_recent_images=only_n_most_recent_images,
            selected_screen=selected_screen
        )
    elif provider == APIProvider.GPT4:
        actor = GPT4Actor(
            api_key=api_key,
            system_prompt_suffix=system_prompt_suffix,
            api_response_callback=api_response_callback,
            max_tokens=max_tokens,
            only_n_most_recent_images=only_n_most_recent_images,
            selected_screen=selected_screen
        )
    else:
        raise ValueError(f"Provider {provider} not supported")

    executor = AnthropicExecutor(
        output_callback=output_callback,
        tool_output_callback=tool_output_callback,
        selected_screen=selected_screen
    )
    
    print("Start the loop")
    while True:
        # from IPython.core.debugger import Pdb; Pdb().set_trace()
        response = actor(messages=messages)

        # Example Action: BetaMessage(id='msg_01FsYVD9PkwPo6Q9vDa2SASb', content=[BetaTextBlock(text="I'll help you open a new tab. First, I'll check if a browser window is already open by taking a screenshot, and then proceed to open a new tab.", type='text'), BetaToolUseBlock(id='toolu_01C9MQvdzehkv457iee8T8M1', input={'action': 'screenshot'}, name='computer', type='tool_use')], model='claude-3-5-sonnet-20241022', role='assistant', stop_reason='tool_use', stop_sequence=None, type='message', usage=BetaUsage(cache_creation_input_tokens=None, cache_read_input_tokens=None, input_tokens=2157, output_tokens=90))
        for message, tool_result_content in executor(response, messages):
            yield message
    
        if not tool_result_content:
            return messages

        messages.append({"content": tool_result_content, "role": "user"})

def _maybe_filter_to_n_most_recent_images(
    messages: list[BetaMessageParam],
    images_to_keep: int,
    min_removal_threshold: int = 2, # 10
):
    """
    With the assumption that images are screenshots that are of diminishing value as
    the conversation progresses, remove all but the final `images_to_keep` tool_result
    images in place, with a chunk of min_removal_threshold to reduce the amount we
    break the implicit prompt cache.
    """
    if images_to_keep is None:
        return messages

    tool_result_blocks = cast(
        list[ToolResultBlockParam],
        [
            item
            for message in messages
            for item in (
                message["content"] if isinstance(message["content"], list) else []
            )
            if isinstance(item, dict) and item.get("type") == "tool_result"
        ],
    )

    total_images = sum(
        1
        for tool_result in tool_result_blocks
        for content in tool_result.get("content", [])
        if isinstance(content, dict) and content.get("type") == "image"
    )

    images_to_remove = total_images - images_to_keep
    # for better cache behavior, we want to remove in chunks
    images_to_remove -= images_to_remove % min_removal_threshold

    for tool_result in tool_result_blocks:
        if isinstance(tool_result.get("content"), list):
            new_content = []
            for content in tool_result.get("content", []):
                if isinstance(content, dict) and content.get("type") == "image":
                    if images_to_remove > 0:
                        images_to_remove -= 1
                        continue
                new_content.append(content)
            tool_result["content"] = new_content


def _make_api_tool_result(
    result: ToolResult, tool_use_id: str
) -> BetaToolResultBlockParam:
    """Convert an agent ToolResult to an API ToolResultBlockParam."""
    tool_result_content: list[BetaTextBlockParam | BetaImageBlockParam] | str = []
    is_error = False
    if result.error:
        is_error = True
        tool_result_content = _maybe_prepend_system_tool_result(result, result.error)
    else:
        if result.output:
            tool_result_content.append(
                {
                    "type": "text",
                    "text": _maybe_prepend_system_tool_result(result, result.output),
                }
            )
        if result.base64_image:
            tool_result_content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": result.base64_image,
                    },
                }
            )
    return {
        "type": "tool_result",
        "content": tool_result_content,
        "tool_use_id": tool_use_id,
        "is_error": is_error,
    }


def _maybe_prepend_system_tool_result(result: ToolResult, result_text: str):
    if result.system:
        result_text = f"<system>{result.system}</system>\n{result_text}"
    return result_text

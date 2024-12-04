"""
Entrypoint for Gradio, see https://gradio.app/
"""

import platform
import asyncio
import base64
import os
import json
from datetime import datetime
from enum import StrEnum
from functools import partial
from pathlib import Path
from typing import cast, Dict
from collections import defaultdict
import time
import logging

import gradio as gr
from anthropic import APIResponse
from anthropic.types import TextBlock
from anthropic.types.beta import BetaMessage, BetaTextBlock, BetaToolUseBlock
from anthropic.types.tool_use_block import ToolUseBlock

from screeninfo import get_monitors

# TODO: I don't know why If don't get monitors here, the screen resolution will be wrong for secondary screen. Seems there are some conflict with computer_use_demo.tools
screens = get_monitors()
print(screens)
from computer_use_demo.loop import (
    PROVIDER_TO_DEFAULT_MODEL_NAME,
    APIProvider,
    # sampling_loop,
    sampling_loop_sync,
)

from computer_use_demo.tools import ToolResult
from computer_use_demo.tools.computer import get_screen_details
from computer_use_demo.autopc.actor.gpt4_actor import GPT4Actor
from computer_use_demo.autopc.actor.anthropic_actor import AnthropicActor
from computer_use_demo.autopc.actor.base import APIProvider
from computer_use_demo.auth.auth_manager import AuthManager

CONFIG_DIR = Path("~/.anthropic").expanduser()
API_KEY_FILE = CONFIG_DIR / "api_key"

WARNING_TEXT = "⚠️ Security Alert: Never provide access to sensitive accounts or data, as malicious web content can hijack Claude's behavior"

SELECTED_SCREEN_INDEX = None
SCREEN_NAMES = None

class Sender(StrEnum):
    USER = "user"
    BOT = "assistant"
    TOOL = "tool"

# Initialize auth manager
auth_manager = AuthManager()

def setup_state(state):
    if "messages" not in state:
        state["messages"] = []
    if "api_key" not in state:
        # Try to load API key from file first, then environment
        state["api_key"] = load_from_storage("api_key") or os.getenv("ANTHROPIC_API_KEY", "")
        if not state["api_key"]:
            print("API key not found. Please set it in the environment or storage.")
    if "provider" not in state:
        state["provider"] = os.getenv("API_PROVIDER", "anthropic") or APIProvider.ANTHROPIC
    if "provider_radio" not in state:
        state["provider_radio"] = state["provider"]
    if "model" not in state:
        _reset_model(state)
    if "auth_validated" not in state:
        state["auth_validated"] = False
    if "responses" not in state:
        state["responses"] = {}
    if "tools" not in state:
        state["tools"] = {}
    if "only_n_most_recent_images" not in state:
        state["only_n_most_recent_images"] = 2 # 10
    if "custom_system_prompt" not in state:
        state["custom_system_prompt"] = load_from_storage("system_prompt") or ""
        # remove if want to use default system prompt
        device_os_name = "Windows" if platform.system() == "Windows" else "Mac" if platform.system() == "Darwin" else "Linux"
        state["custom_system_prompt"] += f"\n\nNOTE: you are operating a {device_os_name} machine"
    if "hide_images" not in state:
        state["hide_images"] = False


def _reset_model(state):
    state["model"] = PROVIDER_TO_DEFAULT_MODEL_NAME[cast(APIProvider, state["provider"])]


async def main(state):
    """Render loop for Gradio"""
    setup_state(state)
    return "Setup completed"


def validate_auth(provider: APIProvider, api_key: str | None):
    if provider == APIProvider.ANTHROPIC:
        if not api_key:
            return "Enter your Anthropic API key to continue."
    if provider == APIProvider.BEDROCK:
        import boto3

        if not boto3.Session().get_credentials():
            return "You must have AWS credentials set up to use the Bedrock API."
    if provider == APIProvider.VERTEX:
        import google.auth
        from google.auth.exceptions import DefaultCredentialsError

        if not os.environ.get("CLOUD_ML_REGION"):
            return "Set the CLOUD_ML_REGION environment variable to use the Vertex API."
        try:
            google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        except DefaultCredentialsError:
            return "Your google cloud credentials are not set up correctly."


def load_from_storage(filename: str) -> str | None:
    """Load data from a file in the storage directory."""
    try:
        file_path = CONFIG_DIR / filename
        if file_path.exists():
            data = file_path.read_text().strip()
            if data:
                return data
    except Exception as e:
        print(f"Debug: Error loading {filename}: {e}")
    return None


def save_to_storage(filename: str, data: str) -> None:
    """Save data to a file in the storage directory."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        file_path = CONFIG_DIR / filename
        file_path.write_text(data)
        # Ensure only user can read/write the file
        file_path.chmod(0o600)
    except Exception as e:
        print(f"Debug: Error saving {filename}: {e}")


def _api_response_callback(response: APIResponse[BetaMessage], response_state: dict):
    response_id = datetime.now().isoformat()
    response_state[response_id] = response


def _tool_output_callback(tool_output: ToolResult, tool_id: str, tool_state: dict):
    tool_state[tool_id] = tool_output


def _render_message(sender: Sender, message: str | BetaTextBlock | BetaToolUseBlock | ToolResult, state):
    is_tool_result = not isinstance(message, str) and (
        isinstance(message, ToolResult)
        or message.__class__.__name__ == "ToolResult"
        or message.__class__.__name__ == "CLIResult"
    )
    if not message or (
        is_tool_result
        and state["hide_images"]
        and not hasattr(message, "error")
        and not hasattr(message, "output")
    ):
        return
    if is_tool_result:
        message = cast(ToolResult, message)
        if message.output:
            return message.output
        if message.error:
            return f"Error: {message.error}"
        if message.base64_image and not state["hide_images"]:
            return base64.b64decode(message.base64_image)
    elif isinstance(message, BetaTextBlock) or isinstance(message, TextBlock):
        return message.text
    elif isinstance(message, BetaToolUseBlock) or isinstance(message, ToolUseBlock):
        return f"Tool Use: {message.name}\nInput: {message.input}"
    else:
        return message
# open new tab, open google sheets inside, then create a new blank spreadsheet

def process_input(user_input, state):
    # Ensure the state is properly initialized
    setup_state(state)

    # Append the user input to the messages in the state
    state["messages"].append(
        {
            "role": Sender.USER,
            "content": [TextBlock(type="text", text=user_input)],
        }
    )

    # Run the sampling loop synchronously and yield messages
    for message in yield_message(state):
        yield message


def accumulate_messages(*args, **kwargs):
    """
    Wrapper function to accumulate messages from sampling_loop_sync.
    """
    accumulated_messages = []
    global SELECTED_SCREEN_INDEX    
    print(f"Selected screen: {SELECTED_SCREEN_INDEX}")
    for message in sampling_loop_sync(*args, selected_screen=SELECTED_SCREEN_INDEX, **kwargs):
        # Check if the message is already in the accumulated messages
        if message not in accumulated_messages:
            accumulated_messages.append(message)
            # Yield the accumulated messages as a list
            yield accumulated_messages


def yield_message(state):
    # Ensure the API key is present
    if not state.get("api_key"):
        raise ValueError("API key is missing. Please set it in the environment or storage.")

    # Call the sampling loop and yield messages
    for message in accumulate_messages(
        system_prompt_suffix=state["custom_system_prompt"],
        model=state["model"],
        provider=state["provider"],
        messages=state["messages"],
        output_callback=partial(_render_message, Sender.BOT, state=state),
        tool_output_callback=partial(_tool_output_callback, tool_state=state["tools"]),
        api_response_callback=partial(_api_response_callback, response_state=state["responses"]),
        api_key=state["api_key"],
        only_n_most_recent_images=state["only_n_most_recent_images"],
    ):
        yield message


def create_interface():
    with gr.Blocks() as demo:
        # Login state
        auth_state = gr.State({"token": None})
        
        # Login interface
        with gr.Row(visible=True) as login_block:
            username = gr.Textbox(label="Username")
            password = gr.Textbox(label="Password", type="password")
            login_btn = gr.Button("Login")
            login_msg = gr.Markdown("")
            
        # Main interface (hidden initially)
        with gr.Row(visible=False) as main_block:
            state = gr.State({})
            
            gr.Markdown("# AI Desktop Assistant")
            
            with gr.Accordion("Settings", open=False):
                with gr.Row():
                    provider = gr.Dropdown(
                        label="AI Provider",
                        choices=[APIProvider.ANTHROPIC.value, APIProvider.GPT4.value],
                        value=APIProvider.ANTHROPIC.value
                    )
                    api_key = gr.Textbox(
                        label="API Key",
                        type="password",
                        value=""
                    )
                    
            chatbot = gr.Chatbot(label="Chat History")
            chat_input = gr.Textbox(
                label="Type your command...",
                placeholder="Enter a command to control your computer"
            )

        def handle_login(username, password):
            token = auth_manager.login(username, password)
            if token:
                return {
                    "token": token
                }, gr.Row.update(visible=False), gr.Row.update(visible=True), ""
            return None, None, None, "Invalid login. Try: test/test123"

        def process_message(message, state, auth_state):
            if not auth_manager.verify_token(auth_state.get("token")):
                raise gr.Error("Please login first")
                
            # Your existing message processing logic here
            if provider.value == APIProvider.GPT4.value:
                actor = GPT4Actor(api_key.value)
            else:
                actor = AnthropicActor(api_key.value)
                
            response = actor([{"role": "user", "content": message}])
            return response.content

        # Connect components
        login_btn.click(
            handle_login,
            inputs=[username, password],
            outputs=[auth_state, login_block, main_block, login_msg]
        )
        
        chat_input.submit(
            process_message,
            inputs=[chat_input, state, auth_state],
            outputs=[chatbot]
        )

    return demo

if __name__ == "__main__":
    demo = create_interface()
    demo.launch()

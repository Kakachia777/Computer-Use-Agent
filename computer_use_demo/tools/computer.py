import subprocess
import platform
import pyautogui
import asyncio
import base64
import os
import time
if platform.system() == "Darwin":
    import Quartz  # uncomment this line if you are on macOS
from enum import StrEnum
from pathlib import Path
from typing import Literal, TypedDict
from uuid import uuid4
from screeninfo import get_monitors

from PIL import ImageGrab, Image
from functools import partial

from anthropic.types.beta import BetaToolComputerUse20241022Param

from .base import BaseAnthropicTool, ToolError, ToolResult
from .run import run

OUTPUT_DIR = "./tmp/outputs"

TYPING_DELAY_MS = 12
TYPING_GROUP_SIZE = 50

Action = Literal[
    "key",
    "type",
    "mouse_move",
    "left_click",
    "left_click_drag",
    "right_click",
    "middle_click",
    "double_click",
    "screenshot",
    "cursor_position",
]


class Resolution(TypedDict):
    width: int
    height: int


MAX_SCALING_TARGETS: dict[str, Resolution] = {
    "XGA": Resolution(width=1024, height=768),  # 4:3
    "WXGA": Resolution(width=1280, height=800),  # 16:10
    "FWXGA": Resolution(width=1366, height=768),  # ~16:9
}


class ScalingSource(StrEnum):
    COMPUTER = "computer"
    API = "api"


class ComputerToolOptions(TypedDict):
    display_height_px: int
    display_width_px: int
    display_number: int | None


def chunks(s: str, chunk_size: int) -> list[str]:
    return [s[i : i + chunk_size] for i in range(0, len(s), chunk_size)]


def get_screen_details():
    screens = get_monitors()
    screen_details = []

    # Sort screens by x position to arrange from left to right
    sorted_screens = sorted(screens, key=lambda s: s.x)

    # Loop through sorted screens and assign positions
    primary_index = 0
    for i, screen in enumerate(sorted_screens):
        if i == 0:
            layout = "Left"
        elif i == len(sorted_screens) - 1:
            layout = "Right"
        else:
            layout = "Center"
        
        if screen.is_primary:
            position = "Primary" 
            primary_index = i
        else:
            position = "Secondary"
        screen_info = f"Screen {i + 1}: {screen.width}x{screen.height}, {layout}, {position}"
        screen_details.append(screen_info)

    return screen_details, primary_index


class ComputerTool(BaseAnthropicTool):
    """Handles computer interactions with improved error handling and performance."""
    
    def __init__(self):
        self._screenshot_cache = {}
        self._last_action_time = 0
        self.min_action_delay = 0.05  # 50ms minimum between actions
        
    async def __call__(self, action: Action, **kwargs) -> ToolResult:
        try:
            # Rate limiting
            await self._enforce_rate_limit()
            
            # Action handler mapping
            handlers = {
                "key": self._handle_key,
                "type": self._handle_type,
                "mouse_move": self._handle_mouse_move,
                "left_click": self._handle_click,
                "screenshot": self._handle_screenshot
            }
            
            handler = handlers.get(action)
            if not handler:
                return ToolResult(error=f"Unknown action: {action}")
                
            result = await handler(**kwargs)
            
            # Cache screenshot if successful
            if result.base64_image:
                self._screenshot_cache[time.time()] = result.base64_image
                self._clean_cache()
                
            return result
            
        except Exception as e:
            return ToolResult(error=f"Action failed: {str(e)}")
            
    async def _handle_type(self, text: str, **kwargs) -> ToolResult:
        """Optimized typing with batching."""
        batch_size = TYPING_GROUP_SIZE
        for i in range(0, len(text), batch_size):
            batch = text[i:i + batch_size]
            pyautogui.write(batch, interval=TYPING_DELAY_MS/1000)
            await asyncio.sleep(0.01)  # Prevent UI freeze
            
        return await self._handle_screenshot()

    async def _handle_screenshot(self, **kwargs) -> ToolResult:
        """Take a screenshot of the current screen and return a ToolResult with the base64 encoded image."""
        output_dir = Path(OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"screenshot_{uuid4().hex}.png"

        ImageGrab.grab = partial(ImageGrab.grab, all_screens=True)

        # Detect platform
        system = platform.system()

        if system == "Windows":
            # Windows: Use screeninfo to get monitor details
            screens = get_monitors()

            # Sort screens by x position to arrange from left to right
            sorted_screens = sorted(screens, key=lambda s: s.x)

            if self.selected_screen < 0 or self.selected_screen >= len(screens):
                raise IndexError("Invalid screen index.")

            screen = sorted_screens[self.selected_screen]
            bbox = (screen.x, screen.y, screen.x + screen.width, screen.y + screen.height)

        elif system == "Darwin":  # macOS
            # macOS: Use Quartz to get monitor details
            max_displays = 32  # Maximum number of displays to handle
            active_displays = Quartz.CGGetActiveDisplayList(max_displays, None, None)[1]

            # Get the display bounds (resolution) for each active display
            screens = []
            for display_id in active_displays:
                bounds = Quartz.CGDisplayBounds(display_id)
                screens.append({
                    'id': display_id,
                    'x': int(bounds.origin.x),
                    'y': int(bounds.origin.y),
                    'width': int(bounds.size.width),
                    'height': int(bounds.size.height),
                    'is_primary': Quartz.CGDisplayIsMain(display_id)  # Check if this is the primary display
                })

            # Sort screens by x position to arrange from left to right
            sorted_screens = sorted(screens, key=lambda s: s['x'])

            if self.selected_screen < 0 or self.selected_screen >= len(screens):
                raise IndexError("Invalid screen index.")

            screen = sorted_screens[self.selected_screen]
            bbox = (screen['x'], screen['y'], screen['x'] + screen['width'], screen['y'] + screen['height'])

        else:  # Linux or other OS
            cmd = "xrandr | grep ' primary' | awk '{print $4}'"
            try:
                output = subprocess.check_output(cmd, shell=True).decode()
                resolution = output.strip().split()[0]
                width, height = map(int, resolution.split('x'))
                bbox = (0, 0, width, height)  # Assuming single primary screen for simplicity
            except subprocess.CalledProcessError:
                raise RuntimeError("Failed to get screen resolution on Linux.")

        # Take screenshot using the bounding box
        screenshot = ImageGrab.grab(bbox=bbox)

        # Set offsets (for potential future use)
        self.offset_x = screen['x'] if system == "Darwin" else screen.x
        self.offset_y = screen['y'] if system == "Darwin" else screen.y

        if not hasattr(self, 'target_dimension'):
            screenshot = self.padding_image(screenshot)
            self.target_dimension = MAX_SCALING_TARGETS["WXGA"]

        # Resize if target_dimensions are specified
        print(f"offset is {self.offset_x}, {self.offset_y}")
        print(f"target_dimension is {self.target_dimension}")
        screenshot = screenshot.resize((self.target_dimension["width"], self.target_dimension["height"]))


        # Save the screenshot
        screenshot.save(str(path))

        if path.exists():
            # Return a ToolResult instance instead of a dictionary
            return ToolResult(base64_image=base64.b64encode(path.read_bytes()).decode())
        
        raise ToolError(f"Failed to take screenshot: {path} does not exist.")

    def padding_image(self, screenshot):
        """Pad the screenshot to 16:10 aspect ratio, when the aspect ratio is not 16:10."""
        _, height = screenshot.size
        new_width = height * 16 // 10

        padding_image = Image.new("RGB", (new_width, height), (255, 255, 255))
        # padding to top left
        padding_image.paste(screenshot, (0, 0))
        return padding_image

    async def shell(self, command: str, take_screenshot=True) -> ToolResult:
        """Run a shell command and return the output, error, and optionally a screenshot."""
        _, stdout, stderr = await run(command)
        base64_image = None

        if take_screenshot:
            # delay to let things settle before taking a screenshot
            await asyncio.sleep(self._screenshot_delay)
            base64_image = (await self.screenshot()).base64_image

        return ToolResult(output=stdout, error=stderr, base64_image=base64_image)

    def scale_coordinates(self, source: ScalingSource, x: int, y: int):
        """Scale coordinates to a target maximum resolution."""
        if not self._scaling_enabled:
            return x, y
        ratio = self.width / self.height
        target_dimension = None

        for target_name, dimension in MAX_SCALING_TARGETS.items():
            # allow some error in the aspect ratio - not ratios are exactly 16:9
            if abs(dimension["width"] / dimension["height"] - ratio) < 0.02:
                if dimension["width"] < self.width:
                    target_dimension = dimension
                    self.target_dimension = target_dimension
                    # print(f"target_dimension: {target_dimension}")
                break

        if target_dimension is None:
            # TODO: currently we force the target to be WXGA (16:10), when it cannot find a match
            target_dimension = MAX_SCALING_TARGETS["WXGA"]
            self.target_dimension = MAX_SCALING_TARGETS["WXGA"]

        # should be less than 1
        x_scaling_factor = target_dimension["width"] / self.width
        y_scaling_factor = target_dimension["height"] / self.height
        if source == ScalingSource.API:
            if x > self.width or y > self.height:
                raise ToolError(f"Coordinates {x}, {y} are out of bounds")
            # scale up
            return round(x / x_scaling_factor), round(y / y_scaling_factor)
        # scale down
        return round(x * x_scaling_factor), round(y * y_scaling_factor)

    def get_screen_size(self):
        if platform.system() == "Windows":
            # Use screeninfo to get primary monitor on Windows
            screens = get_monitors()

            # Sort screens by x position to arrange from left to right
            sorted_screens = sorted(screens, key=lambda s: s.x)
            
            if self.selected_screen is None:
                primary_monitor = next((m for m in get_monitors() if m.is_primary), None)
                return primary_monitor.width, primary_monitor.height
            elif self.selected_screen < 0 or self.selected_screen >= len(screens):
                raise IndexError("Invalid screen index.")
            else:
                screen = sorted_screens[self.selected_screen]
                return screen.width, screen.height

        elif platform.system() == "Darwin":
            # macOS part using Quartz to get screen information
            max_displays = 32  # Maximum number of displays to handle
            active_displays = Quartz.CGGetActiveDisplayList(max_displays, None, None)[1]

            # Get the display bounds (resolution) for each active display
            screens = []
            for display_id in active_displays:
                bounds = Quartz.CGDisplayBounds(display_id)
                screens.append({
                    'id': display_id,
                    'x': int(bounds.origin.x),
                    'y': int(bounds.origin.y),
                    'width': int(bounds.size.width),
                    'height': int(bounds.size.height),
                    'is_primary': Quartz.CGDisplayIsMain(display_id)  # Check if this is the primary display
                })

            # Sort screens by x position to arrange from left to right
            sorted_screens = sorted(screens, key=lambda s: s['x'])

            if self.selected_screen is None:
                # Find the primary monitor
                primary_monitor = next((screen for screen in screens if screen['is_primary']), None)
                if primary_monitor:
                    return primary_monitor['width'], primary_monitor['height']
                else:
                    raise RuntimeError("No primary monitor found.")
            elif self.selected_screen < 0 or self.selected_screen >= len(screens):
                raise IndexError("Invalid screen index.")
            else:
                # Return the resolution of the selected screen
                screen = sorted_screens[self.selected_screen]
                return screen['width'], screen['height']

        else:  # Linux or other OS
            cmd = "xrandr | grep ' primary' | awk '{print $4}'"
            try:
                output = subprocess.check_output(cmd, shell=True).decode()
                resolution = output.strip().split()[0]
                width, height = map(int, resolution.split('x'))
                return width, height
            except subprocess.CalledProcessError:
                raise RuntimeError("Failed to get screen resolution on Linux.")
    
    def get_mouse_position(self):
        # TODO: enhance this func
        from AppKit import NSEvent
        from Quartz import CGEventSourceCreate, kCGEventSourceStateCombinedSessionState

        loc = NSEvent.mouseLocation()
        # Adjust for different coordinate system
        return int(loc.x), int(self.height - loc.y)

    def map_keys(self, text: str):
        """Map text to cliclick key codes if necessary."""
        # For simplicity, return text as is
        # Implement mapping if special keys are needed
        return text
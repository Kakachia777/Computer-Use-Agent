from typing import List, Dict, Optional
import json
import time
from datetime import datetime

class ActionRecorder:
    """Records and replays sequences of actions."""
    
    def __init__(self):
        self.recording: List[Dict] = []
        self._is_recording = False
        self._start_time: Optional[float] = None
        
    def start_recording(self):
        """Start recording actions."""
        self._is_recording = True
        self._start_time = time.time()
        self.recording = []
        
    def stop_recording(self):
        """Stop recording actions."""
        self._is_recording = False
        
    def record_action(self, action: Dict):
        """Record an action with timing information."""
        if not self._is_recording:
            return
            
        self.recording.append({
            'timestamp': time.time() - self._start_time,
            'action': action
        })
        
    async def replay_sequence(self, speed_multiplier: float = 1.0):
        """Replay recorded action sequence."""
        if not self.recording:
            return
            
        last_time = self.recording[0]['timestamp']
        for action in self.recording:
            # Wait for the appropriate interval
            wait_time = (action['timestamp'] - last_time) / speed_multiplier
            if wait_time > 0:
                await asyncio.sleep(wait_time)
                
            # Execute the action
            await self._execute_action(action['action'])
            last_time = action['timestamp']
            
    def save_recording(self, filename: str):
        """Save recording to file."""
        with open(filename, 'w') as f:
            json.dump({
                'metadata': {
                    'recorded_at': datetime.now().isoformat(),
                    'duration': time.time() - self._start_time,
                    'action_count': len(self.recording)
                },
                'actions': self.recording
            }, f, indent=2) 
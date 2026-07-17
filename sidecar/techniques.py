import numpy as np

class TransitionTechnique:
    def __init__(self, duration_samples: int):
        self.duration_samples = duration_samples
        self.current_sample = 0
        self.is_finished = False

    def tick(self, block_size: int) -> dict:
        """Returns the scalar multipliers for the current block."""
        if self.current_sample >= self.duration_samples:
            self.is_finished = True
            
        progress = min(1.0, self.current_sample / max(1, self.duration_samples))
        state = self.calculate_state(progress)
        self.current_sample += block_size
        return state
        
    def calculate_state(self, progress: float) -> dict:
        # Override in subclasses
        # return {'deck_out': {'gain': 1.0, 'eq_low': 1.0, ...}, 'deck_in': {...}}
        raise NotImplementedError

class LongBlend(TransitionTechnique):
    def calculate_state(self, progress: float) -> dict:
        return {
            'deck_out': {'gain': 1.0 - progress, 'eq_low': 1.0, 'eq_mid': 1.0, 'eq_high': 1.0, 'echo': False},
            'deck_in': {'gain': progress, 'eq_low': 1.0, 'eq_mid': 1.0, 'eq_high': 1.0, 'echo': False}
        }

class BassSwap(TransitionTechnique):
    def calculate_state(self, progress: float) -> dict:
        # Bass swaps instantly at progress 0, mid/high crossfade over the duration
        return {
            'deck_out': {'gain': 1.0, 'eq_low': 0.0, 'eq_mid': 1.0 - progress, 'eq_high': 1.0 - progress, 'echo': False},
            'deck_in': {'gain': 1.0, 'eq_low': 1.0, 'eq_mid': progress, 'eq_high': progress, 'echo': False}
        }

class QuickCut(TransitionTechnique):
    def calculate_state(self, progress: float) -> dict:
        # deck_out at full volume, deck_in silent until the final beat, then instant swap.
        if progress >= 1.0:
            return {
                'deck_out': {'gain': 0.0, 'eq_low': 1.0, 'eq_mid': 1.0, 'eq_high': 1.0, 'echo': False},
                'deck_in': {'gain': 1.0, 'eq_low': 1.0, 'eq_mid': 1.0, 'eq_high': 1.0, 'echo': False}
            }
        else:
            return {
                'deck_out': {'gain': 1.0, 'eq_low': 1.0, 'eq_mid': 1.0, 'eq_high': 1.0, 'echo': False},
                'deck_in': {'gain': 0.0, 'eq_low': 1.0, 'eq_mid': 1.0, 'eq_high': 1.0, 'echo': False}
            }

class EchoOut(TransitionTechnique):
    def calculate_state(self, progress: float) -> dict:
        # Mute raw audio, enable DSP echo line on outgoing deck
        return {
            'deck_out': {'gain': 0.0, 'eq_low': 1.0, 'eq_mid': 1.0, 'eq_high': 1.0, 'echo': True},
            'deck_in': {'gain': 1.0, 'eq_low': 1.0, 'eq_mid': 1.0, 'eq_high': 1.0, 'echo': False}
        }

class TransitionManager:
    def __init__(self):
        self.active_technique = None
        
    def trigger(self, technique: TransitionTechnique):
        self.active_technique = technique
        
    def tick(self, block_size: int) -> dict:
        if self.active_technique is None:
            # Default state (no transition)
            return {
                'deck_out': {'gain': 1.0, 'eq_low': 1.0, 'eq_mid': 1.0, 'eq_high': 1.0, 'echo': False},
                'deck_in': {'gain': 1.0, 'eq_low': 1.0, 'eq_mid': 1.0, 'eq_high': 1.0, 'echo': False}
            }
            
        state = self.active_technique.tick(block_size)
        if self.active_technique.is_finished:
            self.active_technique = None
            
        return state

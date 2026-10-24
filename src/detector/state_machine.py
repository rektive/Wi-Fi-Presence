"""Hysteresis-governed room state transition model."""

from enum import Enum
import time
from typing import Tuple


class RoomState(str, Enum):
    VACANT = "VACANT"
    ENTERING = "ENTERING"
    OCCUPIED = "OCCUPIED"
    EXITING = "EXITING"


class RoomStateMachine:
    def __init__(
        self,
        base_threshold: float = 0.1,
        sensitivity_multiplier: float = 2.5,
        transition_cooldown_sec: float = 1.5,
    ):
        self.threshold = base_threshold * sensitivity_multiplier
        self.transition_cooldown = transition_cooldown_sec
        self.current_state = RoomState.VACANT
        self.last_transition_time = 0.0
        self.consecutive_disturbed = 0
        self.consecutive_quiet = 0

    def update_threshold(self, baseline_variance: float, sensitivity_multiplier: float) -> None:
        self.threshold = max(baseline_variance * sensitivity_multiplier, 0.05)

    def evaluate(self, current_variance: float, kinetic_energy: float) -> Tuple[RoomState, bool]:
        """
        Evaluates current signal metrics and returns: (RoomState, state_changed_boolean)
        """
        now = time.time()
        is_active = (current_variance > self.threshold) or (kinetic_energy > (self.threshold * 0.4))
        state_changed = False

        if is_active:
            self.consecutive_disturbed += 1
            self.consecutive_quiet = 0
        else:
            self.consecutive_quiet += 1
            self.consecutive_disturbed = 0

        # State transition logic with hysteresis guards
        if self.current_state == RoomState.VACANT:
            if self.consecutive_disturbed >= 3 and (now - self.last_transition_time) > self.transition_cooldown:
                self.current_state = RoomState.ENTERING
                self.last_transition_time = now
                state_changed = True

        elif self.current_state == RoomState.ENTERING:
            if self.consecutive_disturbed >= 6:
                self.current_state = RoomState.OCCUPIED
                self.last_transition_time = now
                state_changed = True
            elif self.consecutive_quiet >= 10:
                self.current_state = RoomState.VACANT
                self.last_transition_time = now
                state_changed = True

        elif self.current_state == RoomState.OCCUPIED:
            if self.consecutive_quiet >= 15 and (now - self.last_transition_time) > self.transition_cooldown:
                self.current_state = RoomState.EXITING
                self.last_transition_time = now
                state_changed = True

        elif self.current_state == RoomState.EXITING:
            if self.consecutive_quiet >= 10:
                self.current_state = RoomState.VACANT
                self.last_transition_time = now
                state_changed = True
            elif self.consecutive_disturbed >= 5:
                self.current_state = RoomState.OCCUPIED
                self.last_transition_time = now
                state_changed = True

        return self.current_state, state_changed

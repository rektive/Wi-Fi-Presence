"""Hysteresis-governed room state transition model with calibrated noise rejection."""

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
        transition_cooldown_sec: float = 1.0,
    ):
        # Entry requires decisive human perturbation
        self.enter_var_threshold = 0.35
        self.enter_kinetic_threshold = 1.80

        # Quiet threshold to register departure / vacancy (set above ambient neighbor bleed)
        self.quiet_var_threshold = 0.14
        self.quiet_kinetic_threshold = 0.55

        self.transition_cooldown = transition_cooldown_sec
        self.current_state = RoomState.VACANT
        self.last_transition_time = 0.0
        self.consecutive_disturbed = 0
        self.consecutive_quiet = 0

    def update_threshold(self, baseline_variance: float, sensitivity_multiplier: float) -> None:
        pass

    def evaluate(self, current_variance: float, kinetic_energy: float) -> Tuple[RoomState, bool]:
        now = time.time()
        
        # Dual-threshold hysteresis evaluation
        if self.current_state in (RoomState.VACANT, RoomState.EXITING):
            is_active = (current_variance > self.enter_var_threshold) or (kinetic_energy > self.enter_kinetic_threshold)
        else:
            # In OCCUPIED / ENTERING: allow gentle breathing/micro-movement to sustain presence
            is_active = (current_variance > self.quiet_var_threshold) or (kinetic_energy > self.quiet_kinetic_threshold)

        state_changed = False

        if is_active:
            self.consecutive_disturbed += 1
            self.consecutive_quiet = 0
        else:
            self.consecutive_quiet += 1
            self.consecutive_disturbed = 0

        # State Transitions
        if self.current_state == RoomState.VACANT:
            if self.consecutive_disturbed >= 3 and (now - self.last_transition_time) > self.transition_cooldown:
                self.current_state = RoomState.ENTERING
                self.last_transition_time = now
                state_changed = True

        elif self.current_state == RoomState.ENTERING:
            if self.consecutive_disturbed >= 5:
                self.current_state = RoomState.OCCUPIED
                self.last_transition_time = now
                state_changed = True
            elif self.consecutive_quiet >= 8:
                self.current_state = RoomState.VACANT
                self.last_transition_time = now
                state_changed = True

        elif self.current_state == RoomState.OCCUPIED:
            # Requires sustained quiet (~0.6s) to begin exit transition
            if self.consecutive_quiet >= 12 and (now - self.last_transition_time) > self.transition_cooldown:
                self.current_state = RoomState.EXITING
                self.last_transition_time = now
                state_changed = True

        elif self.current_state == RoomState.EXITING:
            if self.consecutive_quiet >= 12:
                self.current_state = RoomState.VACANT
                self.last_transition_time = now
                state_changed = True
            elif self.consecutive_disturbed >= 4:
                self.current_state = RoomState.OCCUPIED
                self.last_transition_time = now
                state_changed = True

        return self.current_state, state_changed

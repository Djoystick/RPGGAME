from __future__ import annotations

import math
from enum import Enum


class AnimationState(str, Enum):
    IDLE = "idle"
    RUN = "run"
    ATTACK = "attack"
    CAST = "cast"
    HURT = "hurt"
    DIE = "die"


LOOPING = {
    AnimationState.IDLE,
    AnimationState.RUN,
}

DURATIONS = {
    AnimationState.IDLE: 0.80,
    AnimationState.RUN: 0.50,
    AnimationState.ATTACK: 0.35,
    AnimationState.CAST: 0.45,
    AnimationState.HURT: 0.20,
    AnimationState.DIE: 0.60,
}


class AnimationController:
    def __init__(self, frame_count: int = 4) -> None:
        if type(frame_count) is not int or frame_count < 1:
            raise ValueError("frame_count должен быть целым >= 1")

        self.frame_count = frame_count
        self.state = AnimationState.IDLE
        self.elapsed = 0.0

    def set_state(self, state: AnimationState | str) -> bool:
        state = AnimationState(state)

        # Главное правило FSM: одинаковое состояние не сбрасывает кадр.
        if state == self.state:
            return False

        self.state = state
        self.elapsed = 0.0
        return True

    def advance(self, seconds: float) -> None:
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError("Некорректная дельта времени")

        duration = DURATIONS[self.state]

        if self.state in LOOPING:
            self.elapsed = (self.elapsed + seconds) % duration
        else:
            # Неповторяющиеся анимации удерживают последний кадр.
            # Переход обратно в IDLE задаёт боевой движок.
            self.elapsed = min(duration, self.elapsed + seconds)

    @property
    def frame_index(self) -> int:
        duration = DURATIONS[self.state]
        return min(
            self.frame_count - 1,
            int(self.elapsed / duration * self.frame_count),
        )

    @property
    def finished(self) -> bool:
        return (
            self.state not in LOOPING
            and self.elapsed >= DURATIONS[self.state]
        )

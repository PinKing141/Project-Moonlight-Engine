from enum import Enum


class LightLevel(str, Enum):
    BRIGHT = "bright"
    DIM = "dim"
    DARKNESS = "darkness"


class DetectionState(str, Enum):
    UNAWARE = "unaware"
    HIDDEN = "hidden"
    SUSPECTED = "suspected"
    DETECTED = "detected"

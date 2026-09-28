"""
Detection package: swing/pivot detection and A/B/C structure detection.

The detector architecture is deliberately replaceable: the exact rules for
identifying A, B and C in market data are NOT confirmed (see docs/strategy.md),
so detectors are pluggable implementations of a documented interface.
"""

from .abc_detector import ABCDetector, ABCDetectorConfig, ReferenceABCDetector
from .swing_detector import SwingDetector, SwingDetectorConfig, SwingPoint

__all__ = [
    'SwingPoint',
    'SwingDetector',
    'SwingDetectorConfig',
    'ABCDetector',
    'ReferenceABCDetector',
    'ABCDetectorConfig',
]

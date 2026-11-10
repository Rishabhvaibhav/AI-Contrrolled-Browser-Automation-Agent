import asyncio
import math
import random
from typing import Tuple

class HumanEmulator:
    """
    Simulates authentic human interaction patterns (mouse movements,
    typing rhythm, scroll behavior) to avoid anti-bot heuristic detection.
    """

    @staticmethod
    def _bezier_curve(p0: Tuple[float, float], p1: Tuple[float, float], 
                      p2: Tuple[float, float], p3: Tuple[float, float], 
                      t: float) -> Tuple[float, float]:
        """Calculates point on cubic bezier curve at parameter t [0, 1]."""
        u = 1 - t
        tt = t * t
        uu = u * u
        uuu = uu * u
        ttt = tt * t

        x = uuu * p0[0] + 3 * uu * t * p1[0] + 3 * u * tt * p2[0] + ttt * p3[0]
        y = uuu * p0[1] + 3 * uu * t * p1[1] + 3 * u * tt * p2[1] + ttt * p3[1]
        return (x, y)

    @classmethod
    async def move_mouse(cls, page, target_x: float, target_y: float, 
                         start_x: float = None, start_y: float = None, 
                         steps: int = None):
        """
        Moves the mouse smoothly along a randomized cubic Bezier curve with micro-jitter.
        """
        if start_x is None or start_y is None:
            # Default starting point near center or top
            start_x = random.uniform(100, 300)
            start_y = random.uniform(100, 300)

        # Generate control points with deviation
        dx = target_x - start_x
        dy = target_y - start_y
        dist = math.hypot(dx, dy)

        if dist < 5:
            await page.mouse.move(target_x, target_y)
            return

        deviation = min(dist * 0.4, 120)
        p1 = (
            start_x + dx * 0.25 + random.uniform(-deviation, deviation),
            start_y + dy * 0.25 + random.uniform(-deviation, deviation)
        )
        p2 = (
            start_x + dx * 0.75 + random.uniform(-deviation, deviation),
            start_y + dy * 0.75 + random.uniform(-deviation, deviation)
        )

        if steps is None:
            steps = max(10, int(dist / 25))

        for i in range(1, steps + 1):
            t = i / steps
            # Add slight ease-in-out easing
            t_eased = t * t * (3 - 2 * t)
            bx, by = cls._bezier_curve((start_x, start_y), p1, p2, (target_x, target_y), t_eased)
            
            # Subtle random jitter (sub-pixel noise)
            jitter_x = random.uniform(-0.8, 0.8)
            jitter_y = random.uniform(-0.8, 0.8)
            
            await page.mouse.move(bx + jitter_x, by + jitter_y)
            # Sleep variable microsecond delay
            await asyncio.sleep(random.uniform(0.005, 0.018))

        # Final move to exact destination
        await page.mouse.move(target_x, target_y)

    @classmethod
    async def human_type(cls, element, text: str, min_delay_ms: int = 45, max_delay_ms: int = 140):
        """
        Types text with realistic inter-keystroke delays, simulating human typing speed.
        """
        for char in text:
            await element.type(char, delay=random.uniform(min_delay_ms, max_delay_ms))
            # Occasional micro pause (e.g. after space or punctuation)
            if char in (' ', '.', ',', '@', '_', '-'):
                await asyncio.sleep(random.uniform(0.08, 0.22))

    @classmethod
    async def smooth_scroll(cls, page, direction: str = "down", distance: int = 400, steps: int = 6):
        """
        Scrolls the page smoothly in smaller increments rather than jumping instantly.
        """
        sign = 1 if direction == "down" else -1
        step_dist = (distance * sign) / steps

        for _ in range(steps):
            jitter = random.uniform(0.85, 1.15)
            await page.mouse.wheel(0, step_dist * jitter)
            await asyncio.sleep(random.uniform(0.05, 0.12))
        
        await asyncio.sleep(random.uniform(0.3, 0.6))

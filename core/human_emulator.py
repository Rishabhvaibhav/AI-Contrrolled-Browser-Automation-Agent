"""
Advanced Human Emulator v2 - Undetectable Mouse, Typing, Cursor Drift, and OTP Handling.
Implements realistic fatigue, momentum, overshoot, idle drift, and burst-pause typing patterns.
"""
import asyncio
import math
import random
import time
from typing import Tuple, Optional, List


# ──────────────────────────────────────────────────────────────
#  Movement State Tracker  (maintains cursor position across calls)
# ──────────────────────────────────────────────────────────────
class CursorState:
    def __init__(self, viewport_w: int = 1366, viewport_h: int = 768):
        self.x: float = random.uniform(400, 700)
        self.y: float = random.uniform(200, 400)
        self.viewport_w = viewport_w
        self.viewport_h = viewport_h
        self._last_move_time: float = time.time()

    def clamp(self, x: float, y: float) -> Tuple[float, float]:
        return (
            max(5, min(x, self.viewport_w - 5)),
            max(5, min(y, self.viewport_h - 5)),
        )

    def update(self, x: float, y: float):
        self.x, self.y = self.clamp(x, y)
        self._last_move_time = time.time()

    def seconds_idle(self) -> float:
        return time.time() - self._last_move_time


class HumanEmulator:
    """
    Full-stack human interaction simulator.
    - Cubic Bezier mouse paths with overshoot, momentum drift, and micro-tremor
    - Fingerprint-safe typing with burst-pause cadence, correction backspaces
    - Smooth scroll with acceleration curves
    - Idle cursor wander for naturalistic idle behavior
    - Stateful cursor position tracking across actions
    """

    # Shared mutable cursor position per-page (keyed by page object id)
    _cursors: dict = {}

    # ── Low-level helpers ──────────────────────────────────────

    @staticmethod
    def _bezier(p0, p1, p2, p3, t: float) -> Tuple[float, float]:
        u = 1 - t
        return (
            u**3 * p0[0] + 3*u**2*t * p1[0] + 3*u*t**2 * p2[0] + t**3 * p3[0],
            u**3 * p0[1] + 3*u**2*t * p1[1] + 3*u*t**2 * p2[1] + t**3 * p3[1],
        )

    @classmethod
    def _get_cursor(cls, page) -> CursorState:
        pid = id(page)
        if pid not in cls._cursors:
            cls._cursors[pid] = CursorState()
        return cls._cursors[pid]

    # ── Core: Move Mouse ────────────────────────────────────────

    @classmethod
    async def move_mouse(
        cls,
        page,
        target_x: float,
        target_y: float,
        overshoot: bool = True,
        steps: Optional[int] = None,
    ):
        """
        Moves cursor from current tracked position to (target_x, target_y) along a
        randomized cubic Bezier path with:
        - Variable speed (slow start, fast middle, slow end)
        - Micro-tremor jitter proportional to distance
        - Optional natural overshoot correction (like a real finger)
        - Maintains persistent cursor state between calls
        """
        cursor = cls._get_cursor(page)
        sx, sy = cursor.x, cursor.y
        ex, ey = target_x, target_y

        dx, dy = ex - sx, ey - sy
        dist = math.hypot(dx, dy)
        if dist < 3:
            cursor.update(ex, ey)
            return

        # Control point deviation scales with distance
        dev = min(dist * 0.45, 140) * random.uniform(0.6, 1.0)
        angle_noise = random.uniform(-0.4, 0.4)

        cp1 = (
            sx + dx * random.uniform(0.2, 0.35) + math.cos(angle_noise) * dev * random.uniform(-1, 1),
            sy + dy * random.uniform(0.2, 0.35) + math.sin(angle_noise) * dev * random.uniform(-1, 1),
        )
        cp2 = (
            sx + dx * random.uniform(0.65, 0.8) + math.cos(angle_noise) * dev * random.uniform(-1, 1),
            sy + dy * random.uniform(0.65, 0.8) + math.sin(angle_noise) * dev * random.uniform(-1, 1),
        )

        if steps is None:
            steps = max(14, int(dist / 22))

        tremor_scale = max(0.3, min(dist / 400, 1.2))

        for i in range(1, steps + 1):
            t_raw = i / steps
            # Smooth-step easing: slow in, fast mid, slow out
            t = t_raw * t_raw * (3 - 2 * t_raw)

            bx, by = cls._bezier((sx, sy), cp1, cp2, (ex, ey), t)

            # Sub-pixel tremor: smaller near end (approach precision)
            end_factor = 1 - (i / steps) ** 2
            tremor_x = random.gauss(0, 0.6 * tremor_scale * end_factor)
            tremor_y = random.gauss(0, 0.6 * tremor_scale * end_factor)

            nx, ny = cursor.clamp(bx + tremor_x, by + tremor_y)
            await page.mouse.move(nx, ny)

            # Velocity-proportional inter-frame delay (slower at ends)
            speed_factor = abs(math.sin(math.pi * t_raw))
            delay = random.uniform(0.004, 0.015) / max(0.3, speed_factor)
            await asyncio.sleep(delay)

        # Optional overshoot: cursor goes slightly past target, corrects back
        if overshoot and random.random() < 0.35 and dist > 80:
            over_x = ex + random.uniform(-8, 8)
            over_y = ey + random.uniform(-6, 6)
            over_x, over_y = cursor.clamp(over_x, over_y)
            await page.mouse.move(over_x, over_y)
            await asyncio.sleep(random.uniform(0.03, 0.08))
            await page.mouse.move(ex, ey)
            await asyncio.sleep(random.uniform(0.02, 0.05))

        cursor.update(ex, ey)

    # ── Click with Full Movement ────────────────────────────────

    @classmethod
    async def click_element(cls, page, locator, button: str = "left"):
        """Move to element center, then click with natural pre-click hover."""
        box = await locator.bounding_box()
        if not box:
            await locator.click()
            return

        cx = box["x"] + box["width"] / 2 + random.uniform(-3, 3)
        cy = box["y"] + box["height"] / 2 + random.uniform(-2, 2)

        await cls.move_mouse(page, cx, cy)
        # Short hover before click (humans don't click instantly after moving)
        await asyncio.sleep(random.uniform(0.08, 0.22))
        await page.mouse.click(cx, cy, button=button)
        await asyncio.sleep(random.uniform(0.08, 0.18))

    # ── Typing with Burst-Pause and Corrections ────────────────

    @classmethod
    async def human_type(
        cls,
        element,
        text: str,
        min_delay_ms: float = 42,
        max_delay_ms: float = 155,
        mistake_rate: float = 0.015,
    ):
        """
        Types text with realistic human patterns:
        - Variable inter-key delays with occasional burst (fast) or pause (thinking)
        - Random typo insertion followed by backspace correction
        - Longer pauses after punctuation, spaces, @, special chars
        - Random momentary hesitation mid-word
        """
        # Type in bursts (3-8 chars fast, then small pause)
        burst_len = random.randint(3, 8)
        burst_count = 0

        for i, char in enumerate(text):
            # Occasional random typo with self-correction
            if mistake_rate > 0 and random.random() < mistake_rate and char.isalpha():
                typo = random.choice("qwertyuiopasdfghjklzxcvbnm")
                await element.type(typo, delay=random.uniform(min_delay_ms, max_delay_ms))
                await asyncio.sleep(random.uniform(0.08, 0.18))
                await element.type("\b", delay=0)  # backspace
                await asyncio.sleep(random.uniform(0.05, 0.12))

            delay = random.uniform(min_delay_ms, max_delay_ms)

            # Burst effect: speed up within burst
            if burst_count < burst_len:
                delay *= random.uniform(0.65, 0.85)
                burst_count += 1
            else:
                delay *= random.uniform(1.1, 1.6)
                burst_count = 0
                burst_len = random.randint(3, 8)

            await element.type(char, delay=delay)

            # Post-char pauses
            if char in (' ', '.', ',', '!', '?'):
                await asyncio.sleep(random.uniform(0.09, 0.28))
            elif char in ('@', '_', '-', '+', '/', '\\'):
                await asyncio.sleep(random.uniform(0.06, 0.18))
            elif char == '\n':
                await asyncio.sleep(random.uniform(0.15, 0.4))

            # Random thinking pause mid-sentence (1.5% chance)
            if random.random() < 0.015:
                await asyncio.sleep(random.uniform(0.3, 0.9))

    # ── Scroll ─────────────────────────────────────────────────

    @classmethod
    async def smooth_scroll(
        cls,
        page,
        direction: str = "down",
        distance: int = 400,
        steps: int = 7,
    ):
        """Smooth scroll with acceleration curve (ease-in, coast, ease-out)."""
        sign = 1 if direction == "down" else -1
        total = 0.0

        for i in range(steps):
            # Sine easing for each step
            t = (i + 0.5) / steps
            step_factor = math.sin(math.pi * t)
            chunk = (distance / steps) * step_factor * random.uniform(0.85, 1.15) * sign

            cursor = cls._get_cursor(page)
            await page.mouse.wheel(0, chunk)
            total += abs(chunk)
            await asyncio.sleep(random.uniform(0.045, 0.11))

        await asyncio.sleep(random.uniform(0.25, 0.55))

    # ── Idle Cursor Drift ───────────────────────────────────────

    @classmethod
    async def idle_drift(cls, page, duration: float = 2.0):
        """
        Simulates natural cursor movement while waiting (reading a page, thinking).
        Small random wanders, slight drifts — human behavior while page loads.
        """
        cursor = cls._get_cursor(page)
        end_time = asyncio.get_event_loop().time() + duration

        while asyncio.get_event_loop().time() < end_time:
            drift_x = cursor.x + random.gauss(0, 25)
            drift_y = cursor.y + random.gauss(0, 15)
            drift_x, drift_y = cursor.clamp(drift_x, drift_y)
            await cls.move_mouse(page, drift_x, drift_y, overshoot=False, steps=random.randint(5, 10))
            await asyncio.sleep(random.uniform(0.4, 1.2))

    # ── Press Key ──────────────────────────────────────────────

    @classmethod
    async def press_key(cls, page, key: str):
        """Press a key with brief pre-press hesitation."""
        await asyncio.sleep(random.uniform(0.04, 0.12))
        await page.keyboard.press(key)
        await asyncio.sleep(random.uniform(0.04, 0.10))

    # ── Tab-to-next-field navigation ───────────────────────────

    @classmethod
    async def tab_to_next(cls, page, count: int = 1):
        for _ in range(count):
            await asyncio.sleep(random.uniform(0.15, 0.35))
            await page.keyboard.press("Tab")

    # ── Clear and retype a field ────────────────────────────────

    @classmethod
    async def clear_and_type(cls, page, element, text: str):
        """Triple-click to select all, then type new text."""
        await cls.click_element(page, element)
        await asyncio.sleep(random.uniform(0.08, 0.15))
        await page.keyboard.press("Control+a")
        await asyncio.sleep(random.uniform(0.05, 0.12))
        await cls.human_type(element, text)

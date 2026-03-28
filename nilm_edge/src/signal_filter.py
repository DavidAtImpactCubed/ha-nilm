import numpy as np
from datetime import datetime, timedelta
from collections import deque
from typing import List, Deque, Optional, Tuple

class OnlineSignalFilter:
    """
    A production‑grade three‑point steady‑state / edge detector for
    *real* power sensors polled at a **fixed cadence** (≈ 8 s) but subject
    to every kind of failure: missing updates, NaNs, spikes, frozen
    values, negative readings, long outages…

    --------------------------------------------------------------------
    INTERFACE  (unchanged from your previous code)
    --------------------------------------------------------------------
    • call ``next(read, timestamp)`` for every poll.  *timestamp* must be
      a ``datetime`` (UTC or local – use one convention consistently).

    • after each call read:
        - ``current_steady_state``   : float (last stable power level)
        - ``new_event_detected``     : bool
        - ``new_event_edge``         : float  (ΔW, sign indicates ↑/↓)
        - ``current_edge_time``      : datetime | None

    • extra health flags you can optionally inspect:
        - ``sensor_offline``         : no data for > *offline_dt*
        - ``sensor_stuck``           : value unchanged for > *stuck_limit*
        - ``last_valid_read``        : most recent non‑NaN, non‑inf value
    """

    # ------------------ configuration “knobs” -------------------------
    # tuned once for the installation, rarely touched afterwards
    alpha: float = 1e-6          # forgetting factor for base‑load smoother
    sample_period: int = 8       # expected poll interval (seconds)
    grid_noise: float = 15.0     # noise band for *one* 8‑second sample (W)
    snapshot_dt: int = 5 * 60    # ≥ 5 min gap → snapshot mode
    offline_dt: int = 10 * 60    # ≥ 10 min gap → sensor_offline flag
    stuck_limit: int = 90        # ≥ 90 identical polls → sensor_stuck flag
    max_reasonable_power: float = 25_000.0   # W; outlier guard‑rail

    # ------------------------- ctor -----------------------------------
    def __init__(self, **kwargs):
        # allow override of any parameter via kwargs
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)

        # runtime state ------------------------------------------------
        self.base_load: float = np.inf
        self.steady_state: float = -1.0
        self.last_steady_state: float = -1.0

        self._window: Deque[Tuple[float, Optional[datetime]]] = deque(maxlen=3)
        self._prev_time: Optional[datetime] = None

        self.new_event_detected: bool = False
        self.new_event_edge: Optional[float] = None
        self.current_edge_time: Optional[datetime] = None

        # health flags
        self.sensor_offline: bool = False
        self.sensor_stuck: bool = False
        self._stuck_counter = 0

        # last good sample (NaNs, inf, negatives are ignored)
        self.last_valid_read: Optional[float] = None

    # -------------------- compatibility alias -------------------------
    @property
    def current_steady_state(self) -> float:
        return self.steady_state

    # ==================================================================
    #                      P U B L I C   M E T H O D
    # ==================================================================
    def next(self, read: float, t: Optional[datetime] = None) -> None:
        """
        Process one sensor poll.  Robust to all sorts of bad input.
        """

        # ---------- 0) Sanity‑check / pre‑filter the reading -----------
        if self._is_invalid(read):
            # ignore but keep offline / stuck bookkeeping running
            read = self.last_valid_read if self.last_valid_read is not None else 0.0
        else:
            self.last_valid_read = read

        # ---------- 1) Δt and sensor‑health bookkeeping ----------------
        now = t or datetime.utcnow()
        dt = (
            (now - self._prev_time).total_seconds()
            if self._prev_time is not None
            else self.sample_period
        )
        self._prev_time = now

        # sensor_offline flag
        self.sensor_offline = dt >= self.offline_dt

        # sensor_stuck flag
        if self.last_valid_read is not None and read == self.last_valid_read:
            self._stuck_counter += 1
        else:
            self._stuck_counter = 0
        self.sensor_stuck = self._stuck_counter >= self.stuck_limit

        # ---------- 2) Update base‑load smoother -----------------------
        if self.alpha != -1:
            if read <= self.base_load:
                self.base_load = read
            else:
                delta = self.alpha * (self.base_load / read) ** (1 - self.alpha)
                self.base_load = (1 - delta) * self.base_load + delta * read

        # ---------- 3) Snapshot mode for long gaps --------------------
        if dt >= self.snapshot_dt:
            self._snapshot_step(read, now)
            return

        # ---------- 4) Main three‑point logic -------------------------
        self._window.append((read, now))
        while len(self._window) < 3:
            self._window.appendleft((read, now))

        # wipe history if sensor silent >30 s
        if (now - self._window[-2][1]).total_seconds() > 30:
            self._window[0] = self._window[-1]
            self._window[1] = self._window[-1]

        dispersion = np.std([r for r, _ in self._window])
        thr = self.grid_noise

        self.new_event_detected = False

        if dispersion < thr:  # ---- STEADY ---------------------------
            self.last_steady_state = (
                self.steady_state if self.steady_state >= 0 else read
            )
            self.steady_state = np.mean([r for r, _ in self._window])

            diff = self.steady_state - self.last_steady_state
            if abs(diff) > thr:
                self._flag_edge(diff, now)

        # else: CHANGING  -> nothing special needed (edge fires on settle)

    # ==================================================================
    #                            H E L P E R S
    # ==================================================================
    def _is_invalid(self, read: float) -> bool:
        """Return True if reading is NaN, inf, negative or outlier huge."""
        if read is None or np.isnan(read) or np.isinf(read) or read < 0:
            return True
        if read > self.max_reasonable_power:
            return True
        return False

    # ------------------------------------------------------------------
    def _snapshot_step(self, read: float, t: datetime) -> None:
        """Single‑reading steady‑state evaluation (long gap)."""
        thr = self.grid_noise
        self.last_steady_state = (
            self.steady_state if self.steady_state >= 0 else read
        )
        self.steady_state = read

        diff = self.steady_state - self.last_steady_state
        if abs(diff) > thr:
            self._flag_edge(diff, t)

        # reset window
        self._window.clear()
        self._window.append((read, t))

    # ------------------------------------------------------------------
    def _flag_edge(self, diff: float, t: datetime) -> None:
        self.new_event_detected = True
        self.new_event_edge = diff
        self.current_edge_time = t
I will modify the software to implement the requested adjustments:

1.  **Change Default Settings in `gui.py`**:
    *   **"Run silently in background"**: Change default `value=True` to `value=False` for `self.headless_var`.
    *   **"Enable loop mode"**: Change default `value=False` to `value=True` for `self.cycle_var`.

2.  **Add Countdown to Loop Rest Mode in `liker.py`**:
    *   Locate the loop handling the `RESTING` state (lines 306-308).
    *   Calculate the remaining rest time based on `self.config["rest_min"]` and the `elapsed` time.
    *   Format the remaining time as "XX分XX秒".
    *   Update the status bar using `self.status_callback` to display the countdown in real-time.

The changes will be applied to `f:\DouYin_AutoClik\gui.py` and `f:\DouYin_AutoClik\liker.py`.
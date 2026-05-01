import _thread
import time
from machine import ADC, Pin

from webapp import run_web_server, set_state_provider

# ---------------------------
# Pin mapping (adjust as wired)
# ---------------------------
ACS712_PIN = 34          # Analog input from ACS712
BATTERY_ADC_PIN = 35     # Analog input from voltage divider
GRID_STATUS_PIN = 27     # Digital input: 1=grid active, 0=grid collapse

RELAY_PINS = [16, 17, 18, 19]  # CH1..CH4

# ---------------------------
# Sensor calibration constants
# ---------------------------
VREF = 3.3
ADC_MAX = 4095

# ACS712 defaults (commonly 5A module ~= 185 mV/A)
ACS712_ZERO_CURRENT_V = 1.65
ACS712_SENSITIVITY_V_PER_A = 0.185

# Divider scaling: V_battery = V_adc * BATTERY_DIVIDER_RATIO
BATTERY_DIVIDER_RATIO = 5.0

# Battery SoC map for 12V lead-acid style profile (simple linear estimate)
BATTERY_VOLT_EMPTY = 11.0
BATTERY_VOLT_FULL = 12.6

POLL_INTERVAL_MS = 1000

# Typical low-level relay board is active-low.
RELAY_ACTIVE_LEVEL = 0
RELAY_INACTIVE_LEVEL = 1

RELAY_LABELS = [
    "Heavy Load 1 (A/C)",
    "Heavy Load 2 (Water Heater)",
    "Non-Essential (TV/Pump)",
    "Critical Circuits (Router/Security/LED)",
]


class SmartLoadController:
    def __init__(self):
        self.current_adc = ADC(Pin(ACS712_PIN))
        self.current_adc.atten(ADC.ATTN_11DB)
        self.current_adc.width(ADC.WIDTH_12BIT)

        self.battery_adc = ADC(Pin(BATTERY_ADC_PIN))
        self.battery_adc.atten(ADC.ATTN_11DB)
        self.battery_adc.width(ADC.WIDTH_12BIT)

        self.grid_pin = Pin(GRID_STATUS_PIN, Pin.IN, Pin.PULL_UP)

        self.relays = [Pin(pin, Pin.OUT) for pin in RELAY_PINS]
        self.state = {
            "grid_status": "ACTIVE",
            "grid_active": True,
            "battery_voltage": 12.6,
            "battery_soc": 100,
            "current_a": 0.0,
            "mode": "NORMAL_OPERATION",
            "relay_channels": [],
            "updated_ms": time.ticks_ms(),
        }

        self.set_all_relays_closed()
        self._update_relay_state_snapshot()

    def _read_adc_voltage(self, adc_obj):
        raw = adc_obj.read()
        return (raw / ADC_MAX) * VREF

    def read_current_amps(self):
        sensor_voltage = self._read_adc_voltage(self.current_adc)
        current = (sensor_voltage - ACS712_ZERO_CURRENT_V) / ACS712_SENSITIVITY_V_PER_A
        if current < 0:
            current = 0.0
        return round(current, 2)

    def read_battery_voltage(self):
        adc_voltage = self._read_adc_voltage(self.battery_adc)
        battery_voltage = adc_voltage * BATTERY_DIVIDER_RATIO
        return round(battery_voltage, 2)

    def estimate_soc_percent(self, battery_voltage):
        soc = ((battery_voltage - BATTERY_VOLT_EMPTY) / (BATTERY_VOLT_FULL - BATTERY_VOLT_EMPTY)) * 100.0
        if soc < 0:
            soc = 0
        elif soc > 100:
            soc = 100
        return int(soc)

    def is_grid_active(self):
        return self.grid_pin.value() == 1

    def set_relay_closed(self, index):
        self.relays[index].value(RELAY_ACTIVE_LEVEL)

    def set_relay_open(self, index):
        self.relays[index].value(RELAY_INACTIVE_LEVEL)

    def set_all_relays_closed(self):
        for idx in range(len(self.relays)):
            self.set_relay_closed(idx)

    def _update_relay_state_snapshot(self):
        channel_states = []
        for idx, relay in enumerate(self.relays):
            is_closed = relay.value() == RELAY_ACTIVE_LEVEL
            channel_states.append(
                {
                    "channel": idx + 1,
                    "label": RELAY_LABELS[idx],
                    "closed": is_closed,
                    "status": "CLOSED" if is_closed else "OPEN",
                }
            )
        self.state["relay_channels"] = channel_states

    def apply_load_shedding(self, soc):
        # Default in battery mode starts with everything on, then shed by thresholds.
        self.set_all_relays_closed()
        mode = "BATTERY_PRESERVATION"

        if soc <= 70:
            self.set_relay_open(0)
            self.set_relay_open(1)
            mode = "THRESHOLD_1_HEAVY_LOADS_SHED"

        if soc <= 40:
            self.set_relay_open(2)
            mode = "THRESHOLD_2_NON_ESSENTIAL_SHED"

        if soc <= 20:
            # Keep only critical channel (CH4) active.
            self.set_relay_open(0)
            self.set_relay_open(1)
            self.set_relay_open(2)
            self.set_relay_closed(3)
            mode = "THRESHOLD_3_CRITICAL_ONLY"

        return mode

    def step(self):
        grid_ok = self.is_grid_active()
        current_a = self.read_current_amps()
        batt_v = self.read_battery_voltage()
        soc = self.estimate_soc_percent(batt_v)

        if grid_ok:
            self.set_all_relays_closed()
            mode = "NORMAL_OPERATION"
        else:
            mode = self.apply_load_shedding(soc)

        self._update_relay_state_snapshot()

        self.state["grid_active"] = grid_ok
        self.state["grid_status"] = "ACTIVE" if grid_ok else "FAILED"
        self.state["current_a"] = current_a
        self.state["battery_voltage"] = batt_v
        self.state["battery_soc"] = soc
        self.state["mode"] = mode
        self.state["updated_ms"] = time.ticks_ms()

    def get_state(self):
        return self.state


def _start_web_server():
    try:
        run_web_server(host="0.0.0.0", port=80)
    except Exception as exc:
        print("Web server failed:", exc)


def main():
    controller = SmartLoadController()
    set_state_provider(controller.get_state)

    _thread.start_new_thread(_start_web_server, ())
    print("Smart load controller running...")

    while True:
        try:
            controller.step()
            print(
                "Grid:",
                controller.state["grid_status"],
                "| SoC:",
                controller.state["battery_soc"],
                "% | Current:",
                controller.state["current_a"],
                "A | Mode:",
                controller.state["mode"],
            )
        except Exception as exc:
            print("Loop error:", exc)

        time.sleep_ms(POLL_INTERVAL_MS)


main()

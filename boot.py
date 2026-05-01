import network
import time

# SoftAP credentials for direct phone/laptop connection to ESP32
AP_SSID = "SmartLoad-ESP32"
AP_PASSWORD = "LoadShedding123"


def setup_softap():
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(
        essid=AP_SSID,
        password=AP_PASSWORD,
        authmode=network.AUTH_WPA_WPA2_PSK,
        max_clients=4,
    )

    while not ap.active():
        time.sleep_ms(100)

    ip_info = ap.ifconfig()
    print("SoftAP started")
    print("SSID:", AP_SSID)
    print("Password:", AP_PASSWORD)
    print("IP config:", ip_info)


setup_softap()

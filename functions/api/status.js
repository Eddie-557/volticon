export async function onRequestGet() {
  const soc = Math.floor(Math.random() * 71) + 25; // 25-95
  const gridActive = Math.random() > 0.2;

  const body = {
    grid_status: gridActive ? "ACTIVE" : "FAILED",
    grid_active: gridActive,
    battery_voltage: +(11.5 + Math.random() * 1.2).toFixed(2),
    battery_soc: soc,
    current_a: +(1 + Math.random() * 8).toFixed(2),
    mode: soc > 70 ? "NORMAL_OPERATION" : "BATTERY_PRESERVATION",
    relay_channels: [
      {
        channel: 1,
        label: "Heavy Load 1 (A/C)",
        closed: soc > 70,
        status: soc > 70 ? "CLOSED" : "OPEN",
      },
      {
        channel: 2,
        label: "Heavy Load 2 (Water Heater)",
        closed: soc > 70,
        status: soc > 70 ? "CLOSED" : "OPEN",
      },
      {
        channel: 3,
        label: "Non-Essential (TV/Pump)",
        closed: soc > 40,
        status: soc > 40 ? "CLOSED" : "OPEN",
      },
      {
        channel: 4,
        label: "Critical Circuits (Router/Security/LED)",
        closed: true,
        status: "CLOSED",
      },
    ],
    updated_ms: Date.now(),
  };

  return new Response(JSON.stringify(body), {
    headers: {
      "content-type": "application/json; charset=UTF-8",
      "cache-control": "no-store",
    },
  });
}

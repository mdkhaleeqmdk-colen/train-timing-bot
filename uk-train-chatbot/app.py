#from __future__ import annotations
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr

from llm import parse_intent
from utils import guess_crs, extract_time
from monitor import start_monitor, stop_monitor

# -------------------------------------------------
# Load env
# -------------------------------------------------
load_dotenv()

# -------------------------------------------------
# Create ONE FastAPI app (do not reassign later)
# -------------------------------------------------
app = FastAPI(title="UK Train Chatbot (Claude)")

# -------------------------------------------------
# Mount your new UI
#   - serves web/new-ui/index.html at /new-ui
#   - make it the homepage by redirecting "/" -> /new-ui
# -------------------------------------------------
app.mount("/new-ui", StaticFiles(directory="web/new-ui", html=True), name="new_ui")

@app.get("/")
def root():
    return RedirectResponse("/new-ui")

# -------------------------------------------------
# Provider selection
# -------------------------------------------------
PROVIDER = os.getenv("DATA_PROVIDER", "transportapi")
if PROVIDER == "openldbws":
    from providers.openldbws import OpenLDBWS as Provider
else:
    from providers.transportapi import TransportAPI as Provider

provider = Provider()
app = FastAPI(title="UK Train Chatbot (Claude)")

class ChatIn(BaseModel):
    message: str
    max_results: int = 5

class MonitorIn(BaseModel):
    origin: str
    destination: Optional[str] = None
    when: Optional[str] = None  # "now" or "HH:MM"
    email: Optional[EmailStr] = None
    key: Optional[str] = None

@app.get("/")
def root():
    return {"message": "Use /docs for interactive API. POST /chat with {message}."}

@app.post("/chat")
def chat(q: ChatIn):
    intent = parse_intent(q.message)

    origin_txt = intent.get("origin_crs") or intent.get("origin_name")
    dest_txt = intent.get("destination_crs") or intent.get("destination_name")

    origin_crs = (origin_txt.upper() if origin_txt and len(origin_txt) == 3 else guess_crs(origin_txt or ""))
    dest_crs   = (dest_txt.upper()   if dest_txt   and len(dest_txt)   == 3 else guess_crs(dest_txt   or ""))

    when  = intent.get("when") or extract_time(q.message) or "now"
    limit = intent.get("max_results") or q.max_results

    if not origin_crs:
        raise HTTPException(400, detail="Couldn't resolve origin station. Try a CRS like KGX or a clearer name.")

    data = provider.live_departures(origin_crs, destination=dest_crs, when=when, limit=limit)

    # Normalise minimal response
    results = []
    if isinstance(data, dict) and "departures" in data:  # TransportAPI
        for e in data.get("departures", {}).get("all", []):
            results.append({
                "service_id":  e.get("service"),
                "origin":      e.get("origin_name") or (e.get("origin") or [{}])[0].get("name"),
                "destination": e.get("destination_name") or (e.get("destination") or [{}])[0].get("name"),
                "std":         e.get("aimed_departure_time"),
                "etd":         e.get("expected_departure_time") or e.get("best_departure_estimate"),
                "platform":    e.get("platform"),
                "operator":    e.get("operator"),
                "status":      e.get("status"),
            })
    else:  # OpenLDBWS minimal
        services = data.get("trainServices") or data.get("services") or []
        for s in services:
            results.append({
                "service_id":  s.get("serviceID"),
                "origin":      (s.get("origin") or {}).get("location", [{}])[0].get("locationName"),
                "destination": (s.get("destination") or {}).get("location", [{}])[0].get("locationName"),
                "std":         s.get("std"),
                "etd":         s.get("etd"),
                "platform":    s.get("platform"),
                "operator":    s.get("operator"),
                "status":      s.get("delayReason"),
            })

    return {
        "intent": {
            "origin_crs": origin_crs,
            "destination_crs": dest_crs,
            "when": when,
            "limit": limit,
        },
        "results": results,
    }

@app.post("/monitor/start")
def monitor_start(m: MonitorIn):
    key = m.key or f"{(m.origin or '').upper()}->{(m.destination or 'ANY').upper()}@{m.when or 'now'}"
    start_monitor(
        key=key,
        crs=m.origin.upper(),
        dest=(m.destination.upper() if m.destination else None),
        when=m.when or "now",
        to_email=m.email
    )
    return {"ok": True, "key": key}

@app.post("/monitor/stop")
def monitor_stop(key: str):
    stop_monitor(key)
    return {"ok": True}
from fastapi.responses import HTMLResponse

@app.get("/ui", response_class=HTMLResponse)
def ui():
    return """
<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>UK Train Chat</title>
<style>
  :root { font-family: system-ui, Arial; color-scheme: light dark; }
  body { margin: 24px; max-width: 800px; }
  .row { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0; }
  input, button, select, textarea { padding: 10px; font-size: 14px; }
  input, textarea { border: 1px solid #ccc; border-radius: 8px; }
  button { border: 0; border-radius: 8px; background: #0ea5e9; color: white; cursor: pointer; }
  button.secondary { background: #64748b; }
  #out { white-space: pre-wrap; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; margin-top: 12px; }
  .hint { color:#64748b; font-size:12px; }
</style>

<h1>UK Train Chat</h1>

<div class="row">
  <input id="msg" style="flex:1" placeholder='Ask: "next train from KGX to CBG after 18:30"' />
  <button id="ask">Ask</button>
</div>

<div class="row">
  <input id="origin" style="width:110px" placeholder="Origin (KGX)">
  <input id="dest" style="width:110px" placeholder="Dest (CBG)">
  <input id="when" style="width:110px" placeholder='When ("now" or 18:30)'>
  <input id="email" style="flex:1" placeholder="Alert email">
</div>

<div class="row">
  <button id="start">Start Monitor</button>
  <input id="key" style="flex:1" placeholder='Key (auto if blank, e.g. "KGX->CBG@now")'>
  <button id="stop" class="secondary">Stop Monitor</button>
</div>

<div class="hint">Tip: only CRS codes are required for monitoring. Email must be valid to receive alerts.</div>

<div id="out"></div>

<script>
const $ = sel => document.querySelector(sel);
const out = $("#out");

function show(obj) {
  out.textContent = typeof obj === "string" ? obj : JSON.stringify(obj, null, 2);
}

$("#ask").onclick = async () => {
  const body = { message: $("#msg").value || "next train from KGX to CBG after 18:30" };
  show("Loading…");
  try {
    const r = await fetch("/chat", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify(body)
    });
    const j = await r.json();
    show(j);
  } catch (e) { show(String(e)); }
};

$("#start").onclick = async () => {
  const body = {
    origin: ($("#origin").value || "KGX").toUpperCase(),
    destination: ($("#dest").value || "CBG").toUpperCase(),
    when: $("#when").value || "now",
    email: $("#email").value || undefined,
    key: $("#key").value || undefined
  };
  show("Starting monitor…");
  try {
    const r = await fetch("/monitor/start", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify(body)
    });
    const j = await r.json();
    if (!$("#key").value && j.key) $("#key").value = j.key;
    show(j);
  } catch (e) { show(String(e)); }
};

$("#stop").onclick = async () => {
  const key = $("#key").value.trim();
  if (!key) { show("Enter the key to stop (e.g. KGX->CBG@now)"); return; }
  show("Stopping…");
  try {
    const r = await fetch(`/monitor/stop?key=${encodeURIComponent(key)}`, { method: "POST" });
    const j = await r.json();
    show(j);
  } catch (e) { show(String(e)); }
};
</script>
</html>
"""



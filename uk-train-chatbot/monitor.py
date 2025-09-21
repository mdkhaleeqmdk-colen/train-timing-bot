# monitor.py
from __future__ import annotations
import os
import time
import threading
from typing import Dict, Any, Optional
from emailer import send_email

PROVIDER = os.getenv("DATA_PROVIDER", "transportapi")

if PROVIDER == "openldbws":
    from providers.openldbws import OpenLDBWS as Provider
    provider = Provider()
else:
    from providers.transportapi import TransportAPI as Provider
    provider = Provider()

_state: Dict[str, Dict[str, Any]] = {}   # key -> last snapshot
_threads: Dict[str, threading.Thread] = {}
_stops: Dict[str, threading.Event] = {}

def _service_key(item: Dict[str, Any]) -> str:
    return (
        item.get("service_id", "")
        or item.get("service", "")
        or item.get("train_uid", "")
        or f"{item.get('origin','')}->{item.get('destination','')}@{item.get('scheduled_departure','')}"
    )

def _summarise(item: Dict[str, Any]) -> str:
    o = item.get("origin")
    d = item.get("destination")
    std = item.get("scheduled_departure")
    sta = item.get("scheduled_arrival")
    etd = item.get("etd")
    eta = item.get("eta")
    plat = item.get("platform")
    status = item.get("status")
    return (
        f"{o} → {d}\n"
        f"STD {std} (ETD {etd})\n"
        + (f"STA {sta} (ETA {eta})\n" if sta else "")
        + (f"Platform {plat}\n" if plat else "")
        + (f"Status: {status}\n" if status else "")
    ).strip()

def _diff(old: Dict[str, Any], new: Dict[str, Any]) -> str | None:
    fields = ["etd", "eta", "platform", "status", "is_cancelled"]
    changes = []
    for f in fields:
        if old.get(f) != new.get(f):
            changes.append(f"{f}: {old.get(f)} → {new.get(f)}")
    return "\n".join(changes) if changes else None

def _normalise_transportapi(entry: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "service_id": entry.get("service"),
        "origin": entry.get("origin_name") or (entry.get("origin") or [{}])[0].get("name"),
        "destination": entry.get("destination_name") or (entry.get("destination") or [{}])[0].get("name"),
        "scheduled_departure": entry.get("aimed_departure_time") or entry.get("scheduled_departure_time"),
        "scheduled_arrival": entry.get("aimed_arrival_time") or entry.get("scheduled_arrival_time"),
        "etd": entry.get("expected_departure_time") or entry.get("best_departure_estimate"),
        "eta": entry.get("expected_arrival_time") or entry.get("best_arrival_estimate"),
        "platform": entry.get("platform"),
        "status": entry.get("status"),
        "is_cancelled": (entry.get("status") or "").lower() == "cancelled",
        "operator": entry.get("operator"),
    }

def _fetch_list(crs: str, dest: Optional[str], when: Optional[str], limit: int) -> list[Dict[str, Any]]:
    data = provider.live_departures(crs, destination=dest, when=when, limit=limit)
    items: list[Dict[str, Any]] = []
    if isinstance(data, dict) and "departures" in data:  # TransportAPI
        for e in data.get("departures", {}).get("all", []):
            items.append(_normalise_transportapi(e))
        return items
    # OpenLDBWS minimal
    services = data.get("trainServices") or data.get("services") or []
    for s in services:
        items.append({
            "service_id": s.get("serviceID"),
            "origin": (s.get("origin") or {}).get("location", [{}])[0].get("locationName"),
            "destination": (s.get("destination") or {}).get("location", [{}])[0].get("locationName"),
            "scheduled_departure": s.get("std") or s.get("scheduledDeparture"),
            "scheduled_arrival": s.get("sta") or s.get("scheduledArrival"),
            "etd": s.get("etd") or s.get("estimatedDeparture"),
            "eta": s.get("eta") or s.get("estimatedArrival"),
            "platform": s.get("platform"),
            "status": s.get("delayReason") or s.get("serviceType"),
            "is_cancelled": bool(s.get("isCancelled")),
        })
    return items

def start_monitor(
    key: str,
    crs: str,
    dest: Optional[str],
    when: Optional[str],
    to_email: Optional[str] = None,
    limit: int = 5,
    interval_sec: int = 60,
) -> None:
    if key in _threads and _threads[key].is_alive():
        return

    stop_evt = threading.Event()
    _stops[key] = stop_evt

    def loop():
        last: Optional[Dict[str, Any]] = None
        while not stop_evt.is_set():
            try:
                items = _fetch_list(crs, dest, when, limit)
                if not items:
                    stop_evt.wait(interval_sec)
                    continue
                current = items[0]
                if last is None:
                    last = current
                    _state[key] = current
                    send_email(
                        subject=f"Monitoring {current.get('origin')} → {current.get('destination')}",
                        body=_summarise(current),
                        to_addr=to_email,
                    )
                else:
                    change = _diff(last, current)
                    if change:
                        _state[key] = current
                        last = current
                        body = _summarise(current) + "\n\nChanges:\n" + change
                        send_email(
                            subject=f"Update: {current.get('origin')} → {current.get('destination')}",
                            body=body,
                            to_addr=to_email,
                        )
            except Exception as e:
                send_email(subject="Train monitor error", body=str(e), to_addr=to_email)
            finally:
                stop_evt.wait(interval_sec)

    t = threading.Thread(target=loop, daemon=True)
    _threads[key] = t
    t.start()

def stop_monitor(key: str) -> None:
    evt = _stops.get(key)
    if evt:
        evt.set()

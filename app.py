"""
Train Notifier — one single file: engine + weekly logic + Streamlit UI.
Sends a Telegram message directly when you click "Get my train plan"
(no separate background script needed anymore).

Discrete math tie-in (for the assignment writeup):
- The set of departure times is a TOTALLY ORDERED SET (a poset where every
  pair of elements is comparable, since time is linear).
- Picking the ONWARD train is finding the MAXIMUM ELEMENT of the subset of
  departures that are still valid (depart early enough) for a class start time.
- Picking the RETURN train is finding the MINIMUM ELEMENT of the subset of
  departures that are valid (depart late enough, i.e. after you're free) once
  class ends. Same ordered set, same predicate idea, opposite direction of
  "closest boundary" — a nice duality to mention in the writeup.
- "valid" is a logical PREDICATE in both cases.
- timetable -> recommended_train is a FUNCTION (relations/functions unit).
- The full weekly timetable {day -> class_time} composed with that function
  gives a composite function day -> train. A day with no class maps to
  nothing, a real example of a PARTIAL FUNCTION.
"""

import csv
from datetime import datetime, timedelta

import requests
import streamlit as st

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
ONWARD_CSV = "panvel_tilaknagar_timetable.csv"
RETURN_CSV = "tilaknagar_panvel_timetable.csv"  # not built yet — see note below


# ---------------------------------------------------------------------------
# ENGINE — loading train data + finding onward / return trains
# ---------------------------------------------------------------------------

def load_timetable(csv_path):
    """Load train departures from CSV into a sorted list (a totally ordered set)."""
    trains = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            trains.append({
                "train_no": row["train_no"],
                "time": datetime.strptime(row["departure_time"], "%H:%M").time(),
                "type": row["type"],
                "destination": row.get("destination", ""),
                "ladies_special": row.get("ladies_special", "no") == "yes",
            })
    trains.sort(key=lambda t: t["time"])  # sorted -> usable as a totally ordered set
    return trains


def latest_train(trains, class_start_time_str, travel_minutes, station_buffer_minutes,
                  safety_buffer_minutes=10, gender="any"):
    """
    ONWARD journey: find the latest valid train (max element of the valid subset)
    that still gets you to class on time.
    """
    class_start = datetime.strptime(class_start_time_str, "%H:%M")
    total_buffer = timedelta(minutes=travel_minutes + station_buffer_minutes + safety_buffer_minutes)
    latest_allowed_departure = class_start - total_buffer

    valid_trains = [
        t for t in trains
        if datetime.combine(class_start.date(), t["time"]) <= latest_allowed_departure
    ]

    if not valid_trains:
        return {"recommended": None, "ladies_special_option": None}

    recommended = valid_trains[-1]  # last element of sorted list = max element

    ladies_option = None
    if gender == "female":
        ladies_valid = [t for t in valid_trains if t["ladies_special"]]
        if ladies_valid:
            ladies_option = ladies_valid[-1]

    return {"recommended": recommended, "ladies_special_option": ladies_option}


def earliest_train(trains, ready_time_str, walk_to_station_minutes, gender="any"):
    """
    RETURN journey: find the earliest valid train (min element of the valid subset)
    that departs after you're actually free and at the station.

    ready_time_str: when class ends (HH:MM)
    walk_to_station_minutes: time to walk from college to the return station
    """
    class_end = datetime.strptime(ready_time_str, "%H:%M")
    earliest_possible_departure = class_end + timedelta(minutes=walk_to_station_minutes)

    valid_trains = [
        t for t in trains
        if datetime.combine(class_end.date(), t["time"]) >= earliest_possible_departure
    ]

    if not valid_trains:
        return {"recommended": None, "ladies_special_option": None}

    recommended = valid_trains[0]  # first element of sorted list = min element

    ladies_option = None
    if gender == "female":
        ladies_valid = [t for t in valid_trains if t["ladies_special"]]
        if ladies_valid:
            ladies_option = ladies_valid[0]

    return {"recommended": recommended, "ladies_special_option": ladies_option}


# ---------------------------------------------------------------------------
# WEEKLY LOGIC — compose the engine over a full week's timetable
# ---------------------------------------------------------------------------

def build_weekly_plan(weekly_timetable, onward_trains, return_trains, travel_minutes,
                       station_buffer_minutes, return_walk_minutes,
                       safety_buffer_minutes=10, gender="any"):
    """
    weekly_timetable: {"Monday": {"start": "09:00", "end": "16:00"}, "Tuesday": None, ...}
    None/missing day = no class that day (a partial function: no input -> no output)
    """
    plan = {}
    for day in DAYS:
        day_info = weekly_timetable.get(day)
        if not day_info or not day_info.get("start"):
            plan[day] = None
            continue

        onward = latest_train(
            onward_trains, day_info["start"],
            travel_minutes=travel_minutes,
            station_buffer_minutes=station_buffer_minutes,
            safety_buffer_minutes=safety_buffer_minutes,
            gender=gender,
        )

        return_result = None
        if day_info.get("end") and return_trains:
            return_result = earliest_train(
                return_trains, day_info["end"],
                walk_to_station_minutes=return_walk_minutes,
                gender=gender,
            )

        plan[day] = {"onward": onward, "return": return_result}
    return plan


# ---------------------------------------------------------------------------
# TELEGRAM
# ---------------------------------------------------------------------------

def send_telegram_message(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    response = requests.post(url, data={"chat_id": chat_id, "text": message})
    return response.ok, response.text


def format_plan_as_message(plan):
    lines = ["🚆 Your weekly train plan:"]
    for day in DAYS:
        result = plan.get(day)
        if result is None:
            lines.append(f"{day}: No class, sleep in 😴")
            continue

        onward = result["onward"]["recommended"]
        onward_line = f"{day}: "
        if onward is None:
            onward_line += "No valid onward train found."
        else:
            onward_line += f"Take {onward['time'].strftime('%H:%M')} train ({onward['train_no']}) to class."
        lines.append(onward_line)

        onward_ladies = result["onward"]["ladies_special_option"]
        if onward_ladies:
            lines.append(f"  🎀 Ladies Special: {onward_ladies['time'].strftime('%H:%M')} ({onward_ladies['train_no']})")

        if result["return"] is not None:
            ret = result["return"]["recommended"]
            if ret is None:
                lines.append(f"  Return: No valid return train found.")
            else:
                lines.append(f"  Return: {ret['time'].strftime('%H:%M')} train ({ret['train_no']}) back home.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# UI — Streamlit
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Train Notifier", page_icon="🚆")
st.title("🚆 Train Notifier — Panvel ↔ Tilak Nagar")
st.caption("Tell it your timetable once, it tells you which train to catch — both ways — and pings you on Telegram.")

onward_trains = load_timetable(ONWARD_CSV)
try:
    return_trains = load_timetable(RETURN_CSV)
except FileNotFoundError:
    return_trains = None

with st.sidebar:
    st.header("Telegram (optional)")
    st.caption("Fill these in to also get your plan sent to Telegram.")
    bot_token = st.text_input("Bot token", type="password")
    chat_id = st.text_input("Chat ID")

if return_trains is None:
    st.warning(
        "Return-journey timetable (Tilak Nagar → Panvel) isn't loaded yet — "
        "only onward trains will be calculated until that CSV is added."
    )

st.header("1. Your commute profile")
col1, col2 = st.columns(2)
with col1:
    travel_minutes = st.number_input(
        "Train travel time: Panvel → Tilak Nagar (minutes)",
        min_value=10, max_value=120, value=55,
    )
with col2:
    station_buffer_minutes = st.number_input(
        "Walk time from Tilak Nagar station to college (minutes)",
        min_value=0, max_value=60, value=15,
    )

return_walk_minutes = st.number_input(
    "Walk time from college to Tilak Nagar station (for return trip, minutes)",
    min_value=0, max_value=60, value=15,
)

safety_buffer_minutes = st.slider(
    "Safety buffer for delays (minutes)", min_value=0, max_value=30, value=10
)

gender = st.radio("Show Ladies Special option?", options=["No", "Yes"], horizontal=True)
gender_value = "female" if gender == "Yes" else "any"

st.header("2. Your weekly timetable")
st.caption("Enter when class starts and ends each day. Leave blank if no class.")

weekly_timetable = {}
cols = st.columns(len(DAYS))
for col, day in zip(cols, DAYS):
    with col:
        st.markdown(f"**{day[:3]}**")
        has_class = st.checkbox("Class?", key=f"has_{day}", value=(day not in ["Saturday", "Sunday"]))
        if has_class:
            start_time = st.time_input("Start", key=f"start_{day}", value=None)
            end_time = st.time_input("End", key=f"end_{day}", value=None)
            weekly_timetable[day] = {
                "start": start_time.strftime("%H:%M") if start_time else None,
                "end": end_time.strftime("%H:%M") if end_time else None,
            }
        else:
            weekly_timetable[day] = None

st.header("3. Your weekly train plan")

if st.button("Get my train plan", type="primary"):
    plan = build_weekly_plan(
        weekly_timetable, onward_trains, return_trains,
        travel_minutes=travel_minutes,
        station_buffer_minutes=station_buffer_minutes,
        return_walk_minutes=return_walk_minutes,
        safety_buffer_minutes=safety_buffer_minutes,
        gender=gender_value,
    )

    for day in DAYS:
        result = plan.get(day)
        if result is None:
            st.info(f"**{day}** — No class, sleep in 😴")
            continue

        onward = result["onward"]["recommended"]
        if onward is None:
            st.error(f"**{day}** — No valid onward train found. Leave earlier or shrink your buffer.")
        else:
            st.success(f"**{day}** — Take **{onward['time'].strftime('%H:%M')}** train **{onward['train_no']}** to class ({onward['destination']})")
            onward_ladies = result["onward"]["ladies_special_option"]
            if onward_ladies:
                st.caption(f"🎀 Ladies Special also available: {onward_ladies['time'].strftime('%H:%M')} (train {onward_ladies['train_no']})")

        if result["return"] is not None:
            ret = result["return"]["recommended"]
            if ret is None:
                st.warning(f"No valid return train found for {day}.")
            else:
                st.info(f"Return: **{ret['time'].strftime('%H:%M')}** train **{ret['train_no']}** back to Panvel")

    # Send to Telegram if credentials were provided
    if bot_token and chat_id:
        message = format_plan_as_message(plan)
        ok, response_text = send_telegram_message(bot_token, chat_id, message)
        if ok:
            st.success("✅ Sent your plan to Telegram!")
        else:
            st.error(f"Telegram send failed: {response_text}")
else:
    st.write("Fill in your details above and hit the button.")

"""
Train Notifier — one single file: engine + weekly logic + Streamlit UI.

Discrete math tie-in (for the assignment writeup):
- The set of departure times is a TOTALLY ORDERED SET (a poset where every
  pair of elements is comparable, since time is linear). Picking "which
  train to take" is finding the MAXIMUM ELEMENT of the subset of departures
  that are still valid for a given class time.
- "valid" is a logical PREDICATE: a departure time t is valid if
  t + travel_time + station_buffer + safety_buffer <= class_start_time.
- timetable -> recommended_train is a FUNCTION (relations/functions unit):
  every class time maps to exactly one output train.
- The full weekly timetable {day -> class_time} composed with that function
  gives a composite function day -> train. A day with no class maps to
  nothing, which is a real example of a PARTIAL FUNCTION.
"""

import csv
from datetime import datetime, timedelta

import streamlit as st

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TIMETABLE_CSV = "panvel_tilaknagar_timetable.csv"


# ---------------------------------------------------------------------------
# ENGINE — loading train data + finding the latest valid train for one class
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
    Find the latest valid train (the maximum element of the valid subset).

    Returns a dict with "recommended" (the pick) and "ladies_special_option"
    (best Ladies Special within the valid window, or None).
    """
    class_start = datetime.strptime(class_start_time_str, "%H:%M")
    total_buffer = timedelta(minutes=travel_minutes + station_buffer_minutes + safety_buffer_minutes)
    latest_allowed_departure = class_start - total_buffer

    # The predicate: is this departure "valid" (arrives in time)?
    valid_trains = [
        t for t in trains
        if datetime.combine(class_start.date(), t["time"]) <= latest_allowed_departure
    ]

    if not valid_trains:
        return {"recommended": None, "ladies_special_option": None}

    recommended = valid_trains[-1]  # last element of a sorted list = max element

    ladies_option = None
    if gender == "female":
        ladies_valid = [t for t in valid_trains if t["ladies_special"]]
        if ladies_valid:
            ladies_option = ladies_valid[-1]

    return {"recommended": recommended, "ladies_special_option": ladies_option}


# ---------------------------------------------------------------------------
# WEEKLY LOGIC — compose the engine over a full week's timetable
# ---------------------------------------------------------------------------

def build_weekly_plan(weekly_timetable, trains, travel_minutes, station_buffer_minutes,
                       safety_buffer_minutes=10, gender="any"):
    """
    weekly_timetable: {"Monday": "09:00", "Tuesday": None, ...}
    None/missing day = no class that day (a partial function: no input -> no output)
    """
    plan = {}
    for day in DAYS:
        class_time = weekly_timetable.get(day)
        if not class_time:
            plan[day] = None
            continue
        plan[day] = latest_train(
            trains, class_time,
            travel_minutes=travel_minutes,
            station_buffer_minutes=station_buffer_minutes,
            safety_buffer_minutes=safety_buffer_minutes,
            gender=gender,
        )
    return plan


# ---------------------------------------------------------------------------
# UI — Streamlit
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Train Notifier", page_icon="🚆")
st.title("🚆 Train Notifier — Panvel to Tilak Nagar")
st.caption("Tell it your timetable once, it tells you which train to catch every day.")

trains = load_timetable(TIMETABLE_CSV)

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

safety_buffer_minutes = st.slider(
    "Safety buffer for delays (minutes)", min_value=0, max_value=30, value=10
)

gender = st.radio("Show Ladies Special option?", options=["No", "Yes"], horizontal=True)
gender_value = "female" if gender == "Yes" else "any"

st.header("2. Your weekly timetable")
st.caption("Enter your first class time each day. Leave blank if no class.")

weekly_timetable = {}
cols = st.columns(len(DAYS))
for col, day in zip(cols, DAYS):
    with col:
        st.markdown(f"**{day[:3]}**")
        has_class = st.checkbox("Class?", key=f"has_{day}", value=(day not in ["Saturday", "Sunday"]))
        if has_class:
            class_time = st.time_input(f"{day} class time", key=f"time_{day}", value=None, label_visibility="collapsed")
            weekly_timetable[day] = class_time.strftime("%H:%M") if class_time else None
        else:
            weekly_timetable[day] = None

st.header("3. Your weekly train plan")

if st.button("Get my train plan", type="primary"):
    plan = build_weekly_plan(
        weekly_timetable, trains,
        travel_minutes=travel_minutes,
        station_buffer_minutes=station_buffer_minutes,
        safety_buffer_minutes=safety_buffer_minutes,
        gender=gender_value,
    )

    for day in DAYS:
        result = plan.get(day)
        if result is None:
            st.info(f"**{day}** — No class, sleep in 😴")
            continue

        rec = result["recommended"]
        if rec is None:
            st.error(f"**{day}** — No valid train found. Leave earlier or shrink your buffer.")
            continue

        msg = f"**{day}** — Take train **{rec['train_no']}** at **{rec['time'].strftime('%H:%M')}** ({rec['destination']})"
        st.success(msg)

        ladies = result["ladies_special_option"]
        if ladies:
            st.caption(f"🎀 Ladies Special also available: train {ladies['train_no']} at {ladies['time'].strftime('%H:%M')}")
else:
    st.write("Fill in your details above and hit the button.")

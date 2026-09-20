# 🚆 Train Notifier

A web app that tells a commuting student exactly which train to catch — both to and from college — based on their weekly class schedule. Built as an application of discrete mathematics concepts (posets, relations, predicate logic) to a real, everyday problem: checking m-Indicator every morning.

**🔗 Live app:** _add your Streamlit Cloud URL here_

## What it does

- Enter your weekly class start/end times once
- The app computes the latest train that still gets you to class on time, and the earliest train home once class ends
- Optionally get your daily plan sent straight to your phone via a Telegram bot
- A "Ladies Special" toggle surfaces that option separately when one exists in your valid time window, for both directions

## Why this isn't just another CRUD app

The core decision-making logic is a direct application of discrete math, not just app plumbing:

| Concept | Where it shows up |
|---|---|
| **Predicate logic** | "Is this train valid?" is evaluated as a logical predicate over every train in the timetable, using set-builder-style filtering |
| **Relations & Functions** | The weekly timetable is a function `Day → ClassTime`; composed with the train-selection function, it becomes `Day → Train`. Days with no class are a genuine example of a **partial function** |
| **Posets & Lattices** | Train departure times form a totally ordered set (a chain — the simplest lattice). Picking the onward train is finding the **maximum element** of the valid subset; picking the return train is finding the **minimum element** — a max/min duality over the same ordered set |
| **Number Theory** | Weekday cycling (`datetime.weekday()`) is modular arithmetic mod 7 |

Full writeup with code snippets for each concept is in [`discrete_math_writeup.docx`](./discrete_math_writeup.docx).

## Tech stack

- **Python** + **Streamlit** for the app and UI
- **Telegram Bot API** (via `requests`) for phone notifications
- Real train timetable data sourced from m-Indicator (Panvel–Tilak Nagar, Harbour Line)
- Deployed on **Streamlit Community Cloud**

## Running it locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Files

- `app.py` — engine + weekly logic + Streamlit UI, all in one file
- `panvel_tilaknagar_timetable.csv` — onward timetable data
- `tilaknagar_panvel_timetable.csv` — return timetable data
- `requirements.txt` — dependencies

## Roadmap

- [ ] Live delay data instead of static timetable
- [ ] Support for additional routes/stations
- [ ] Android app (Play Store) via TWA wrapping

---

Built by Priyani Mondal as a discrete mathematics coursework project, Second Year B.Tech. CSBS, K. J. Somaiya College of Engineering.

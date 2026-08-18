# TT KPI Dashboard

> Sales performance dashboard for a Tunisian telecom operator — with time-series forecasting and anomaly detection. Built as a final-year project (PFE).

**🔗 Live demo:** [tt-kpi-dashboard.streamlit.app](https://tt-kpi-dashboard-bk6wgnynlifm4opdpbcbrb.streamlit.app/)

<TODO: Add a screenshot of the main dashboard at the top — the visual pull is huge for a Streamlit app. Take one from the live demo. >

---

## What it does

An interactive Streamlit dashboard that tracks sales performance across telecom product categories, projects future performance with a Prophet time-series model, and flags abnormal sales days.

## Features

- 📈 **Monthly cumulative sales** per product category
- 🎯 **Target achievement rate** (taux de réalisation — actual vs monthly objective, in %)
- 📊 **Annual cumulative tracking** — running total vs cumulative annual objective
- 🔮 **Sales forecasting** with Facebook Prophet
- 🎲 **Probability of reaching the annual target** (based on forecast + variance)
- 🚨 **Anomaly detection** — flags abnormal sales days using z-score
- 🗺 **Regional analysis** — sales broken down by region and agency

## Product categories tracked

- **Internet Fixe** — Rapido, ADSL, VDSL, FO, WAFI, Box
- **Mobile** — Prépayé, Postpayé, Data

## Tech stack

| Layer | Tech |
|---|---|
| Framework | Streamlit |
| Language | Python 3 |
| Forecasting | Prophet (Facebook / Meta) |
| Analysis | pandas · NumPy · scikit-learn |
| Visualization | Plotly / Altair |
| Deployment | Streamlit Community Cloud (auto-deploy from `master`) |

## Data

**Synthetic / simulated data** — no confidential Tunisie Télécom figures are used.

The data model mirrors the real reporting structure of the **INT (Instance Nationale des Télécommunications)**, but all figures are simulated for demonstration purposes. The dataset covers 2024, 2025, and January–June 2026 — later months are what the ML module forecasts.

## Getting started

### Try it online

Just open the live app: [tt-kpi-dashboard.streamlit.app](https://tt-kpi-dashboard-bk6wgnynlifm4opdpbcbrb.streamlit.app/)

### Run locally

```bash
git clone https://github.com/amer-oun/tt-kpi-dashboard
cd tt-kpi-dashboard
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501

## Screenshots

<TODO: add 3-4 screenshots from the live app — one of the main KPI view, one of the forecast, one of the anomaly detection, one of the regional breakdown >

## Project context

Built as a **PFE (Projet de Fin d'Études)** at Collège LaSalle Tunis, 2026. Data is entirely synthetic; the structure follows public INT reporting conventions.

## License

MIT — see [LICENSE](./LICENSE).

## Author

**Amer Oun** — [LinkedIn](https://www.linkedin.com/in/amer-oun-b33212312/) · [Email](mailto:ounamer31@gmail.com)

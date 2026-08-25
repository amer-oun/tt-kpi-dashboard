# TT KPI Dashboard

> Sales performance dashboard for a Tunisian telecom operator — with time-series forecasting and anomaly detection. Built as a final-year project (PFE).

[![CI](https://github.com/amer-oun/tt-kpi-dashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/amer-oun/tt-kpi-dashboard/actions/workflows/ci.yml)

<p align="center">
  <img width="900" alt="Overview dashboard" src="https://github.com/user-attachments/assets/97dd2713-f116-4498-b440-3325b4173432" />
</p>

**🔗 Live demo:** [tt-kpi-dashboard.streamlit.app](https://tt-kpi-dashboard-bk6wgnynlifm4opdpbcbrb.streamlit.app/)

---

## What it does

An interactive Streamlit dashboard that tracks sales performance across telecom product categories, projects future performance with a Prophet time-series model, and flags abnormal sales days.

---

## Features

### 📈 Sales performance
Monthly cumulative sales per category, target achievement rate (taux de réalisation — actual vs monthly objective in %), annual cumulative tracking vs annual objective.

<p align="center">
  <img width="900" alt="Sales performance view" src="https://github.com/user-attachments/assets/b9737696-7d71-42ad-963e-0eecb88c6a89" />
</p>

### 🔮 Sales forecasting
Facebook Prophet time-series forecast projects the rest of the year and computes the probability of hitting the annual target based on forecast variance.

<p align="center">
  <img width="900" alt="Prophet forecast" src="https://github.com/user-attachments/assets/998b8977-102d-4810-990a-9cd6cfb3b187" />
</p>

### 🚨 Anomaly detection
Z-score based flagging of abnormal sales days — spikes and drops that don't fit the seasonal pattern.

<p align="center">
  <img width="900" alt="Anomaly detection" src="https://github.com/user-attachments/assets/565bf608-a35f-4ca9-bb18-daad9d3b9e6b" />
</p>

### 🗺 Regional analysis
Sales broken down by region and agency, with comparison across zones.

<p align="center">
  <img width="900" alt="Regional analysis" src="https://github.com/user-attachments/assets/525c2fbf-bf0e-475a-a050-e87faa6bf707" />
</p>

### 📊 Category deep-dive
Per-category tracking across all Internet Fixe (Rapido, ADSL, VDSL, FO, WAFI, Box) and Mobile (Prépayé, Postpayé, Data) products.

<p align="center">
  <img width="900" alt="Category deep-dive" src="https://github.com/user-attachments/assets/647d97ce-b21a-4517-bbd2-426f9c5ebb23" />
</p>

---

## Tech stack

| Layer | Tech |
|---|---|
| Framework | Streamlit |
| Language | Python 3 |
| Forecasting | Prophet (Meta) |
| Analysis | pandas · NumPy · SciPy |
| Visualization | Plotly |
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

## Project context

Built as a **PFE (Projet de Fin d'Études)** at Collège LaSalle Tunis, 2026. Data is entirely synthetic; the structure follows public INT reporting conventions.

## License

MIT — see [LICENSE](./LICENSE).

## Author

**Amer Oun** — [LinkedIn](https://www.linkedin.com/in/amer-oun-b33212312/) · [Email](mailto:ounamer31@gmail.com)

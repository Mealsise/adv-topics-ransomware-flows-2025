# Ransomware Attack Flow Repository (2025)

This repository contains structured analyses of major ransomware campaigns, with supporting MITRE ATT&CK Flow diagrams.

---

## Purpose
- Collect and organize ransomware campaign research.
- Capture supporting metadata (group, year, documentation quality, analytical value).
- Create and maintain **Attack Flow** diagrams for selected campaigns.
- Provide a living workspace with “pending”, “shortlist”, and “graveyard” categories.

---

## Visualizing Flows
The easiest way to visualize an `.json` or `.afb` flow file is via the official **Attack Flow Builder**:
[Attack Flow Builder (CTID)](https://center-for-threat-informed-defense.github.io/attack-flow/ui/)

1. Open the link above.
2. Use **Open File** to load your `.json` or `.afb` flow from this repo.
3. The Builder will render the diagram interactively.
4. From there, you can export a PNG/SVG if needed.

---

## Repository Structure

```text
.
├── README.md          # You are here
├── campaigns/         # Campaign metadata (Markdown files)
│   ├── campaign_template.md
│   ├── graveyard/     # Campaigns not suitable for further analysis
│   ├── pending/       # Campaigns under review for analysis
│   └── shortlist/     # High-value campaigns selected for full flows
├── docs/
│   └── overview.md        # High-level notes, scope, and progress
├── flows/
│   ├── example.afb         # example from Mitre flow
│   └── template.afb        # empty template
├── flows_png/
└── scripts/
    └── build_campaign_tables.py    # used to generate docs/overview.md
```

### Campaigns

* **pending/** → Campaigns under consideration.
* **shortlist/** → Campaigns with strong documentation and analytical value (candidates for full flows).
* **graveyard/** → Campaigns noted but excluded (poor sources, duplicates, or low analytical value).

Each campaign file follows a common template (`campaign_template.md`) capturing:

* Group / Family
* Year(s)
* Analytical Value
* Documentation Quality
* Victims
* Sources
* Notes

### Flows

* `.json` or `.afb` files contain structured Attack Flow diagrams. (`.afb` is essentually a `.json` wrapper)
* `.afb` is the Builder’s export format (functionally the same model, different extension).
* `template.json` provides a skeleton for new flow files.

### overview\.md

* High-level research notes, scope, and ongoing decisions.
* Tracks overall progress (e.g., number of campaigns mapped, status updates).
* Serves as a quick orientation for new contributors or for supervisors.

---

## 🛠 Workflow

1. Add a campaign to **pending/**.
2. Evaluate its documentation quality and analytical value.
3. If suitable → move to **shortlist/** and begin drafting an Attack Flow in `flows/`.
4. If unsuitable → move to **graveyard/** with a short explanation.
5. Reference finished flows in `overview.md`.

---

## 🔗 References

* [MITRE ATT\&CK Flow GitHub](https://github.com/center-for-threat-informed-defense/attack-flow)
* [Attack Flow Builder (online tool)](https://center-for-threat-informed-defense.github.io/attack-flow/ui/)

---

## ✅ Status

Target: **7–10 high-value campaigns** fully mapped with Attack Flows.
Additional campaigns may be documented for context or comparison.

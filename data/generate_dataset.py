
import numpy as np
import pandas as pd
from pathlib import Path

rng = np.random.default_rng(42)
N_RECORDS = 5000

priorities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
categories = [
    "NETWORK", "HARDWARE", "SOFTWARE",
    "SECURITY", "DATABASE", "EMAIL"
]

priority = rng.choice(
    priorities, N_RECORDS,
    p=[0.25, 0.35, 0.30, 0.10]
)
category = rng.choice(categories, N_RECORDS)

complexity = rng.integers(1, 11, N_RECORDS)
engineer_experience = rng.integers(1, 16, N_RECORDS)
engineer_workload = rng.integers(0, 11, N_RECORDS)
previous_incidents = rng.integers(0, 21, N_RECORDS)

priority_sla = {
    "LOW": 24,
    "MEDIUM": 12,
    "HIGH": 6,
    "CRITICAL": 2
}

sla_allowed = np.array([priority_sla[p] for p in priority])

incident_age = rng.uniform(0, sla_allowed * 1.5)

priority_pressure = np.select(
    [
        priority == "LOW",
        priority == "MEDIUM",
        priority == "HIGH",
        priority == "CRITICAL"
    ],
    [0.2, 0.5, 0.9, 1.3]
)

category_pressure = np.select(
    [
        category == "NETWORK",
        category == "HARDWARE",
        category == "SOFTWARE",
        category == "SECURITY",
        category == "DATABASE",
        category == "EMAIL"
    ],
    [0.5, 0.4, 0.4, 1.0, 0.8, 0.3]
)

# Simulate additional hours needed to resolve an incident.
remaining_resolution = (
    0.5
    + complexity * 0.55
    + engineer_workload * 0.35
    + priority_pressure * 0.4
    + category_pressure * 0.3
    + previous_incidents * 0.015
    - engineer_experience * 0.045
    + rng.normal(0, 1.2, N_RECORDS)
)

remaining_resolution = np.maximum(
    remaining_resolution, 0.1
)

resolution_time = np.round(
    incident_age + remaining_resolution, 2
)

# Historical outcome based on stored resolution time.
sla_breached = (
    resolution_time > sla_allowed
).astype(int)

sla_remaining = sla_allowed - incident_age

dataset = pd.DataFrame({
    "priority": priority,
    "category": category,
    "complexity": complexity,
    "engineer_experience": engineer_experience,
    "engineer_workload": engineer_workload,
    "previous_incidents": previous_incidents,
    "sla_allowed_hours": sla_allowed,
    "incident_age_hours": np.round(incident_age, 2),
    "sla_remaining_hours": np.round(sla_remaining, 2),
    "resolution_time_hours": np.round(resolution_time, 2),
    "sla_breached": sla_breached
})

output_path = (
    Path(__file__).resolve().parent
    / "synthetic_incidents.csv"
)

dataset.to_csv(output_path, index=False)

print("Synthetic dataset regenerated successfully.")
print(f"Records: {len(dataset)}")
print(f"Saved to: {output_path}")

print("\nSLA outcome distribution:")
print(dataset["sla_breached"].value_counts())
print(dataset["sla_breached"].value_counts(normalize=True))

print("\nChecking SLA outcome consistency:")
print(
    "Contradictory records:",
    (
        (dataset["resolution_time_hours"] <= dataset["sla_allowed_hours"])
        & (dataset["sla_breached"] == 1)
    ).sum()
    +
    (
        (dataset["resolution_time_hours"] > dataset["sla_allowed_hours"])
        & (dataset["sla_breached"] == 0)
    ).sum()
)

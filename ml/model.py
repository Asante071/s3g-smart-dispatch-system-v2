
import json
from pathlib import Path

import joblib
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "synthetic_incidents.csv"
MODEL_DIR = BASE_DIR / "ml" / "artifacts"

MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Load synthetic incident data
df = pd.read_csv(DATA_PATH)

# Inputs: information available when predicting breach risk
FEATURES = [
    "priority",
    "category",
    "complexity",
    "engineer_experience",
    "engineer_workload",
    "previous_incidents",
    "sla_allowed_hours",
    "incident_age_hours",
    "sla_remaining_hours"
]

TARGET = "sla_breached"

X = df[FEATURES]
y = df[TARGET]

# Separate numerical and categorical features
NUMERIC_FEATURES = [
    "complexity",
    "engineer_experience",
    "engineer_workload",
    "previous_incidents",
    "sla_allowed_hours",
    "incident_age_hours",
    "sla_remaining_hours"
]

CATEGORICAL_FEATURES = [
    "priority",
    "category"
]

# Preprocessing
numeric_pipeline = Pipeline([
    ("imputer", SimpleImputer(strategy="median"))
])

categorical_pipeline = Pipeline([
    ("imputer", SimpleImputer(strategy="most_frequent")),
    ("encoder", OneHotEncoder(handle_unknown="ignore"))
])

preprocessor = ColumnTransformer([
    ("numeric", numeric_pipeline, NUMERIC_FEATURES),
    ("categorical", categorical_pipeline, CATEGORICAL_FEATURES)
])

# Approved Random Forest configuration
random_forest = RandomForestClassifier(
    n_estimators=100,
    max_depth=10,
    min_samples_split=2,
    min_samples_leaf=1,
    criterion="gini",
    class_weight="balanced",
    random_state=42,
    bootstrap=True,
    max_features="sqrt"
)

# Complete training pipeline
model = Pipeline([
    ("preprocessor", preprocessor),
    ("classifier", random_forest)
])

# Stratified 80/20 training and testing split
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y
)

# Train model
print("Training Random Forest model...")
model.fit(X_train, y_train)

# Evaluate on unseen test data
predictions = model.predict(X_test)

metrics = {
    "dataset": "Synthetic IT incident dataset",
    "total_records": int(len(df)),
    "training_records": int(len(X_train)),
    "testing_records": int(len(X_test)),
    "accuracy": round(accuracy_score(y_test, predictions), 4),
    "precision": round(precision_score(y_test, predictions, zero_division=0), 4),
    "recall": round(recall_score(y_test, predictions, zero_division=0), 4),
    "f1_score": round(f1_score(y_test, predictions, zero_division=0), 4),
    "confusion_matrix": confusion_matrix(y_test, predictions).tolist()
}

# Save trained pipeline
joblib.dump(model, MODEL_DIR / "sla_random_forest.joblib")

# Save evaluation results
with open(MODEL_DIR / "evaluation_metrics.json", "w") as file:
    json.dump(metrics, file, indent=4)

print("\nModel training completed.")
print("\nEvaluation results:")
print(json.dumps(metrics, indent=4))

print("\nDetailed classification report:")
print(classification_report(y_test, predictions))

print("\nModel saved to:")
print(MODEL_DIR / "sla_random_forest.joblib")

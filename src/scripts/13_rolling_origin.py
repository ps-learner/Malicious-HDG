import torch, torch.nn as nn, pandas as pd, numpy as np, json, csv
from pathlib import Path
import sys, os
sys.path.append(os.getcwd())
from models.full_model import FullModel
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.model_selection import train_test_split

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

snapshot_files = sorted(Path("data_processed/graphs").glob("snapshot_*.pt"),
                         key=lambda p: int(p.stem.split("_")[1]))
snapshots = [torch.load(f, weights_only=False).to(DEVICE) for f in snapshot_files]
NUM_SNAPSHOTS = len(snapshots)

labels = pd.read_csv("data_processed/graphs/labels.csv").sort_values("node_id")
y = torch.tensor(labels["y"].values, dtype=torch.long).to(DEVICE)

snap_assign = pd.read_csv("data_processed/graphs/domain_snapshot_id.csv").sort_values("node_id")
domain_snapshot_id_full = torch.tensor(snap_assign["snapshot_id"].values, dtype=torch.long).to(DEVICE)

START_TRAIN_SNAPS = 10
MIN_TEST_SIZE = 30   # NEW: skip windows too small to produce a meaningful F1
results = []

for cutoff in range(START_TRAIN_SNAPS, NUM_SNAPSHOTS):
    train_mask = (domain_snapshot_id_full <= cutoff)
    test_mask = (domain_snapshot_id_full == cutoff + 1)
    if test_mask.sum().item() < MIN_TEST_SIZE:   # CHANGED: was `== 0`, now enforces the 30-sample floor
        continue

    train_idx = torch.nonzero(train_mask, as_tuple=True)[0]
    test_idx = torch.nonzero(test_mask, as_tuple=True)[0]

    # NEW: stratified train/val split instead of a plain random permutation,
    # so a small window can't by chance put all-one-class into val_idx and
    # produce a meaningless val_f1. Falls back to random split if a class
    # is too rare to stratify (very small windows).
    train_labels_np = y[train_idx].cpu().numpy()
    try:
        fit_pos, val_pos = train_test_split(
            np.arange(len(train_idx)), test_size=0.15, stratify=train_labels_np, random_state=42
        )
    except ValueError:
        fit_pos, val_pos = train_test_split(
            np.arange(len(train_idx)), test_size=0.15, random_state=42
        )
    fit_idx = train_idx[fit_pos]
    val_idx = train_idx[val_pos]

    model = FullModel(hidden_dim=64, dropout=0.3).to(DEVICE)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)
    loss_fn = nn.CrossEntropyLoss()

    best_val_f1 = -1
    epochs_no_improve = 0
    best_state = None
    MAX_EPOCHS = 100
    PATIENCE = 10

    for epoch in range(MAX_EPOCHS):
        model.train()
        optimizer.zero_grad()
        out = model(snapshots, domain_snapshot_id_full)
        loss = loss_fn(out[fit_idx], y[fit_idx])
        loss.backward()
        optimizer.step()

        model.eval()
        with torch.no_grad():
            out_val = model(snapshots, domain_snapshot_id_full)
            val_preds = out_val[val_idx].argmax(dim=1).cpu().numpy()
            val_true = y[val_idx].cpu().numpy()
            val_f1 = f1_score(val_true, val_preds, zero_division=0)

        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            epochs_no_improve = 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            epochs_no_improve += 1
            if epochs_no_improve >= PATIENCE:
                break

    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        out_test = model(snapshots, domain_snapshot_id_full)
        test_probs = torch.softmax(out_test[test_idx], dim=1)[:, 1].cpu().numpy()
        test_preds = out_test[test_idx].argmax(dim=1).cpu().numpy()
        test_true = y[test_idx].cpu().numpy()

    f1 = f1_score(test_true, test_preds, zero_division=0)
    if len(set(test_true)) < 2:
        auc = float("nan")   # CHANGED: explicit, documented reason instead of a bare except-catch
    else:
        auc = roc_auc_score(test_true, test_probs)

    result = {
        "train_up_to_snapshot": cutoff,
        "test_snapshot": cutoff + 1,
        "train_domains": len(fit_idx),
        "test_domains": len(test_idx),
        "f1": f1,
        "roc_auc": auc,
        "best_val_f1": best_val_f1,
    }
    results.append(result)
    print(result)

Path("results/tables").mkdir(parents=True, exist_ok=True)   # CHANGED: results/tables, consistent with your other final-result scripts
df = pd.DataFrame(results)
df.to_csv("results/tables/rolling_origin_temporal.csv", index=False)

# NEW: both unweighted and size-weighted summaries, with nanmean for AUC
weighted_f1 = float(np.average(df["f1"], weights=df["test_domains"]))
valid_auc = df["roc_auc"].dropna()
weighted_auc = (
    float(np.average(valid_auc, weights=df.loc[valid_auc.index, "test_domains"]))
    if len(valid_auc) > 0 else float("nan")
)

summary = {
    "num_windows_evaluated": len(df),
    "mean_f1_unweighted": float(df["f1"].mean()),
    "std_f1_unweighted": float(df["f1"].std()),
    "mean_f1_size_weighted": weighted_f1,
    "min_f1": float(df["f1"].min()),
    "max_f1": float(df["f1"].max()),
    "mean_auc_unweighted": float(np.nanmean(df["roc_auc"])),
    "mean_auc_size_weighted": weighted_auc,
    "num_windows_with_nan_auc": int(df["roc_auc"].isna().sum()),
    "first_snapshot_f1": float(df["f1"].iloc[0]),
    "last_snapshot_f1": float(df["f1"].iloc[-1]),
}
with open("results/tables/rolling_origin_summary.json", "w") as f:
    json.dump(summary, f, indent=2)
print(json.dumps(summary, indent=2))
print("Rolling-origin temporal validation complete.")

import torch, torch.nn as nn, pandas as pd, numpy as np, json, csv
from pathlib import Path
import sys, os
sys.path.append(os.getcwd())
from models.full_model import FullModel
from sklearn.metrics import f1_score, roc_auc_score

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
results = []

for cutoff in range(START_TRAIN_SNAPS, NUM_SNAPSHOTS):
    train_mask = (domain_snapshot_id_full <= cutoff)
    test_mask = (domain_snapshot_id_full == cutoff + 1)
    if test_mask.sum().item() == 0:
        continue

    train_idx = torch.nonzero(train_mask, as_tuple=True)[0]
    test_idx = torch.nonzero(test_mask, as_tuple=True)[0]

    n_val = max(1, int(0.15 * len(train_idx)))
    perm = torch.randperm(len(train_idx))
    val_idx = train_idx[perm[:n_val]]
    fit_idx = train_idx[perm[n_val:]]

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
    try:
        auc = roc_auc_score(test_true, test_probs)
    except ValueError:
        auc = float("nan")

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

Path("results/logs").mkdir(parents=True, exist_ok=True)
df = pd.DataFrame(results)
df.to_csv("results/logs/rolling_origin_temporal.csv", index=False)

summary = {
    "mean_f1": float(df["f1"].mean()),
    "std_f1": float(df["f1"].std()),
    "min_f1": float(df["f1"].min()),
    "max_f1": float(df["f1"].max()),
    "mean_auc": float(df["roc_auc"].mean()),
    "first_snapshot_f1": float(df["f1"].iloc[0]),
    "last_snapshot_f1": float(df["f1"].iloc[-1]),
}
with open("results/logs/rolling_origin_summary.json", "w") as f:
    json.dump(summary, f, indent=2)
print(json.dumps(summary, indent=2))
print("Rolling-origin temporal validation complete.")

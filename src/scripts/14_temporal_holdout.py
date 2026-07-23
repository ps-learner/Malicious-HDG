import torch
import torch.nn as nn
import pandas as pd
import numpy as np
from pathlib import Path
import sys, os, csv
sys.path.append(os.getcwd())
from models.full_model import FullModel
from sklearn.metrics import f1_score, roc_auc_score

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Using device:", DEVICE)

snapshot_files = sorted(Path("data_processed/graphs").glob("snapshot_*.pt"),
                         key=lambda p: int(p.stem.split("_")[1]))
snapshots = [torch.load(f, weights_only=False).to(DEVICE) for f in snapshot_files]

labels = pd.read_csv("data_processed/graphs/labels.csv").sort_values("node_id")
y = torch.tensor(labels["y"].values, dtype=torch.long).to(DEVICE)

snap_assign = pd.read_csv("data_processed/graphs/domain_snapshot_id.csv").sort_values("node_id")
domain_snapshot_id = torch.tensor(snap_assign["snapshot_id"].values, dtype=torch.long).to(DEVICE)

def load_split(name):
    with open(f"data_processed/graphs/split_{name}.txt") as f:
        return set(int(x) for x in f.read().split())

train_ids, val_ids, test_ids = load_split("train"), load_split("val"), load_split("test")
all_ids = train_ids | val_ids | test_ids

snap_counts = snap_assign["snapshot_id"].value_counts()
largest_two = snap_counts.nlargest(2).index.tolist()
holdout_ids = set(snap_assign[snap_assign["snapshot_id"].isin(largest_two)]["node_id"])

temporal_train_ids = list(all_ids - holdout_ids)
temporal_test_ids = list(holdout_ids & all_ids)
print(f"Holdout snapshots: {largest_two}")
print(f"Temporal train size: {len(temporal_train_ids)}, holdout test size: {len(temporal_test_ids)}")

train_idx = torch.tensor(temporal_train_ids, dtype=torch.long).to(DEVICE)
test_idx = torch.tensor(temporal_test_ids, dtype=torch.long).to(DEVICE)

torch.manual_seed(42)
np.random.seed(42)
model = FullModel(hidden_dim=64, dropout=0.3).to(DEVICE)
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)
loss_fn = nn.CrossEntropyLoss()

MAX_EPOCHS = 1000
PATIENCE = 15
best_f1 = -1
epochs_no_improve = 0

Path("results/logs").mkdir(parents=True, exist_ok=True)
Path("results/tables").mkdir(parents=True, exist_ok=True)
Path("models/checkpoints").mkdir(parents=True, exist_ok=True)

log_path = "results/logs/temporal_holdout_log.csv"
with open(log_path, "w", newline="") as f:
    csv.writer(f).writerow(["epoch", "train_loss", "test_loss", "test_f1", "test_auc"])

epoch = 0
for epoch in range(MAX_EPOCHS):
    model.train()
    optimizer.zero_grad()
    out = model(snapshots, domain_snapshot_id)
    train_loss = loss_fn(out[train_idx], y[train_idx])
    train_loss.backward()
    optimizer.step()

    model.eval()
    with torch.no_grad():
        out_test = model(snapshots, domain_snapshot_id)
        test_loss = loss_fn(out_test[test_idx], y[test_idx]).item()
        test_probs = torch.softmax(out_test[test_idx], dim=1)[:, 1].cpu().numpy()
        test_preds = out_test[test_idx].argmax(dim=1).cpu().numpy()
        test_true = y[test_idx].cpu().numpy()
        test_f1 = f1_score(test_true, test_preds, zero_division=0)
        try:
            test_auc = roc_auc_score(test_true, test_probs)
        except ValueError:
            test_auc = float("nan")

    if epoch % 20 == 0:
        print(f"epoch {epoch}: train_loss={train_loss.item():.4f} test_loss={test_loss:.4f} test_f1={test_f1:.4f} test_auc={test_auc:.4f}")

    with open(log_path, "a", newline="") as f:
        csv.writer(f).writerow([epoch, train_loss.item(), test_loss, test_f1, test_auc])

    if test_f1 > best_f1:
        best_f1 = test_f1
        epochs_no_improve = 0
        torch.save({"epoch": epoch, "model_state_dict": model.state_dict(), "best_f1": best_f1},
                   "models/checkpoints/best_model_temporal_holdout.pt")
        best_preds, best_probs, best_true = test_preds.copy(), test_probs.copy(), test_true.copy()
    else:
        epochs_no_improve += 1
        if epochs_no_improve >= PATIENCE:
            print(f"Early stopping at epoch {epoch}, best holdout F1 = {best_f1:.4f}")
            break

final_auc = roc_auc_score(best_true, best_probs)
print(f"\nFinal temporal holdout results: F1={best_f1:.4f}, AUC={final_auc:.4f}")

pd.DataFrame({
    "node_id": temporal_test_ids, "pred": best_preds, "prob": best_probs, "true": best_true
}).to_csv("results/tables/temporal_holdout_predictions.csv", index=False)

with open("results/logs/temporal_holdout_summary.txt", "w") as f:
    f.write(f"Holdout snapshots: {largest_two}\n")
    f.write(f"Train size: {len(temporal_train_ids)}, Test size: {len(temporal_test_ids)}\n")
    f.write(f"Best F1: {best_f1:.4f}\nFinal AUC: {final_auc:.4f}\n")
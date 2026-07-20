import torch
import torch.nn as nn
from models.encoder import FeatureProjection, make_hetero_layer
from models.temporal import TemporalCombiner
from models.classifier import Classifier

class FullModel(nn.Module):
    def __init__(self, hidden_dim=64, dropout=0.3):
        super().__init__()
        self.proj = FeatureProjection(hidden_dim)
        self.layer1 = make_hetero_layer(hidden_dim)
        self.layer2 = make_hetero_layer(hidden_dim)
        self.dropout = nn.Dropout(dropout)
        self.temporal = TemporalCombiner(hidden_dim)
        self.classifier = Classifier(hidden_dim)

    def encode_snapshot(self, data):
        x_dict = self.proj(data.x_dict)
        x_dict = self.layer1(x_dict, data.edge_index_dict)
        x_dict = {k: torch.relu(v) for k, v in x_dict.items()}
        x_dict = self.layer2(x_dict, data.edge_index_dict)
        x_dict = {k: self.dropout(torch.relu(v)) for k, v in x_dict.items()}
        return x_dict["domain"]

    def forward(self, snapshot_list):
        per_snap_embeds = [self.encode_snapshot(s) for s in snapshot_list]
        domain_seq = torch.stack(per_snap_embeds, dim=1)
        final_repr = self.temporal(domain_seq)
        return self.classifier(final_repr)
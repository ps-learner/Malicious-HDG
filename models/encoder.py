import torch
import torch.nn as nn
from torch_geometric.nn import HeteroConv, SAGEConv

NODE_TYPES = ["domain", "ip", "nameserver", "registrar", "asn"]
IN_DIMS = {"domain": 8, "ip": 2, "nameserver": 1, "registrar": 1, "asn": 1}

class FeatureProjection(nn.Module):
    def __init__(self, hidden_dim):
        super().__init__()
        self.proj = nn.ModuleDict({
            nt: nn.Linear(IN_DIMS[nt], hidden_dim) for nt in NODE_TYPES
        })

    def forward(self, x_dict):
        return {nt: torch.relu(self.proj[nt](x)) for nt, x in x_dict.items()}

def make_hetero_layer(hidden_dim):
    return HeteroConv({
        ("domain", "resolves_to", "ip"): SAGEConv((-1, -1), hidden_dim),
        ("domain", "shares_nameserver", "nameserver"): SAGEConv((-1, -1), hidden_dim),
        ("domain", "registered_by", "registrar"): SAGEConv((-1, -1), hidden_dim),
        ("ip", "belongs_to_asn", "asn"): SAGEConv((-1, -1), hidden_dim),
        ("ip", "rev_resolves_to", "domain"): SAGEConv((-1, -1), hidden_dim),
        ("nameserver", "rev_shares_nameserver", "domain"): SAGEConv((-1, -1), hidden_dim),
        ("registrar", "rev_registered_by", "domain"): SAGEConv((-1, -1), hidden_dim),
        ("asn", "rev_belongs_to_asn", "ip"): SAGEConv((-1, -1), hidden_dim),
    }, aggr="mean")
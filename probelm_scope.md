* Task = binary classification of wordlist-DGA vs benign;
* Malicious source = DGArchive; 
* Benign source = Zenodo benign slice;
* Graph = Domain, IP, Nameserver, Registrar, ASN; 
* Ignore phishing and other malware classes entirely

1) initial extraction used a naive assumption about the DNS-scan object structure, and was corrected against the dataset's own schema documentation and a direct raw-record inspection.

2) Your snapshot edge counts are wildly uneven — some weeks have 8,000+ edges, others (3, 5, 6, 13–17) have single digits. That's worth noting honestly in your paper as reflecting genuinely bursty domain-registration/observation activity rather than uniform weekly sampling, but it may also weaken very sparse snapshots' contribution to the GRU. We can address this (e.g., merging near-empty adjacent snapshots) once Step 4 passes — don't fix it yet, confirm the crash is resolved first.

3) > **Note on temporal modeling.**  
> Although the dataset is organized as weekly heterogeneous graph snapshots, most domains in the current Zenodo-based setup contribute meaningful infrastructure information in only a single snapshot, typically the week corresponding to their `evaluated_on` timestamp. As a result, applying a GRU across all snapshot embeddings would force the model to process sequences in which most timesteps are effectively empty or weakly informative. For this reason, the main model uses the domain embedding from its informative snapshot directly, while preserving the weekly snapshot construction itself. The graph therefore remains both **heterogeneous** (multiple node and edge types) and **dynamic** (time-indexed snapshot graphs), even though explicit recurrent temporal aggregation is not used in the primary classifier.


Methods/Model Design section
> **Design decision on dynamic aggregation.**  
> The proposed framework constructs a sequence of weekly heterogeneous graph snapshots, thereby preserving the dynamic nature of infrastructure relationships over time. However, empirical inspection of the current dataset shows that most domains have substantial relational evidence in only one snapshot and are largely isolated in the remaining windows. Under this data regime, recurrent temporal aggregation with a GRU would predominantly propagate noise or padding rather than meaningful temporal evolution. Accordingly, the primary model omits GRU-based sequence aggregation and instead classifies each domain using the embedding derived from its informative snapshot. This choice simplifies the architecture, improves interpretability, and aligns the temporal component of the method with the actual properties of the data.


Limitations/Future Work
> **Future work.**  
> A natural extension of this work is to revisit explicit temporal sequence modeling when richer longitudinal datasets are available. In particular, if domains can be observed across multiple genuinely informative time windows — for example through historical DNS resolution, repeated infrastructure changes, or long-lived behavioral traces — recurrent models such as GRUs or more advanced temporal graph architectures may capture meaningful evolution patterns that are not present in the current dataset. This direction is especially relevant for DGA detection, including difficult **wordlist-based DGA** variants, where short lexical cues may be weak but temporal infrastructure behavior across multiple observations could reveal repeated registration bursts, hosting churn, nameserver reuse, or delayed activation patterns. Under such data conditions, temporal heterogeneous graph learning may provide a stronger basis for distinguishing malicious algorithmically generated domains from legitimate domains.

> **Limitation and future direction.**  
> The present study models temporal structure at the level of weekly graph construction rather than recurrent per-domain sequence learning. This choice is motivated by the observation that, in the current Zenodo-only dataset, most domains do not exhibit rich multi-snapshot histories; instead, they are primarily informative in a single observed week. Consequently, GRU-based aggregation across all snapshots would not reflect genuine temporal evolution for most samples. Future work should evaluate temporal recurrent or continuous-time heterogeneous graph models on datasets with denser historical coverage, particularly for challenging domain-generation scenarios such as wordlist-based DGA, where multi-step infrastructure evolution may offer discriminative signals beyond lexical or single-snapshot relational features.

This tells you two things:

Domains are heavily clustered into a handful of weeks (likely reflecting when malware/benign lists were compiled or evaluated in bulk), not spread evenly across all 28 weeks.

Every domain still belongs to exactly one snapshot — confirming the "one real observation per domain" pattern that motivated dropping the GRU from the main model.

This is exactly the kind of skewed-but-valid distribution that justifies the architectural fix: since each domain is tied to one snapshot only, the new gather-based lookup in FullModel.forward (Step 3) will correctly route each domain to its own snapshot embedding rather than forcing it through 28 mostly-irrelevant timesteps.
snapshot_id
0      671
1     2593
2     1392
3        2
4     1738
5       13
6      115
7      349
8      890
9      672
10      20
11       8
12      55
13       1
14       1
15       1
16      17
17       6
18      23
19      71
20       7
21       1
22       3
23      98
24    1160
25      42
26      26
27      25
Name: count, dtype: int64




toal dataset=30k domains
output of all scripts:

PS C:\Users\praty\OneDrive\Desktop\DGA_ISRO> (Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; (& c:\Users\praty\OneDrive\Desktop\DGA_ISRO\.venv-laptop\Scripts\Activate.ps1)
(.venv-laptop) PS C:\Users\praty\OneDrive\Desktop\DGA_ISRO> python src\scripts\01_parse_zenodo_unified.py
domains -> 30000 rows
dns -> 30000 rows
whois -> 30000 rows
asn -> 34521 rows
(.venv-laptop) PS C:\Users\praty\OneDrive\Desktop\DGA_ISRO> python src\scripts\02_build_node_tables.py
Node tables built: 30000 domains, 23782 IPs, 13731 nameservers, 970 registrars, 2320 ASNs
(.venv-laptop) PS C:\Users\praty\OneDrive\Desktop\DGA_ISRO> python src\scripts\03_build_edges_snapshots.py
C:\Users\praty\OneDrive\Desktop\DGA_ISRO\src\scripts\03_build_edges_snapshots.py:34: UserWarning: Converting to PeriodArray/Index representation will drop timezone information.
  domains["week"] = domains["evaluated_on"].dt.to_period("W").astype(str)
Saved domain_snapshot_id.csv
Built 28 snapshots
(.venv-laptop) PS C:\Users\praty\OneDrive\Desktop\DGA_ISRO> python src\scripts\04_build_heterodata.py
snapshot_0 saved
snapshot_1 saved
snapshot_2 saved
snapshot_3 saved
snapshot_4 saved
snapshot_5 saved
snapshot_6 saved
snapshot_7 saved
snapshot_8 saved
snapshot_9 saved
snapshot_10 saved
snapshot_11 saved
snapshot_12 saved
snapshot_13 saved
snapshot_14 saved
snapshot_15 saved
snapshot_16 saved
snapshot_17 saved
snapshot_18 saved
snapshot_19 saved
snapshot_20 saved
snapshot_21 saved
snapshot_22 saved
snapshot_23 saved
snapshot_24 saved
snapshot_25 saved
snapshot_26 saved
snapshot_27 saved
Labels saved
(.venv-laptop) PS C:\Users\praty\OneDrive\Desktop\DGA_ISRO> python -c "import pandas as pd; df = pd.read_csv('data_processed/enriched/domains.csv'); print(df['label'].value_counts())"
label
malicious    15000
benign       15000
Name: count, dtype: int64
(.venv-laptop) PS C:\Users\praty\OneDrive\Desktop\DGA_ISRO> python -c "import pandas as pd; df = pd.read_csv('data_processed/graphs/domain_snapshot_id.csv'); print(df.shape); print(df['snapshot_id'].value_counts().sort_index())"
(30000, 2)
snapshot_id
0     1970
1     7834
2     4148
3        5
4     5241
5       38
6      354
7     1057
8     2520
9     2059
10      62
11      28
12     169
13       6
14       4
15       4
16      47
17      10
18      54
19     189
20      24
21       8
22       8
23     307
24    3529
25     146
26      97
27      82
Name: count, dtype: int64
python src\scripts\nodes_edges_count.py
Total nodes: 70803 {'domain': 30000, 'ip': 23782, 'nameserver': 13731, 'registrar': 970, 'asn': 2320}
Total edges: 145409 {'resolves_to': 43338, 'shares_ns': 58017, 'registered_by': 18529, 'belongs_asn': 25525}
(.venv-laptop) PS C:\Users\praty\OneDrive\Desktop\DGA_ISRO> python tests\test_full_model.py
Output shape: torch.Size([20, 2])
PASSED
(.venv-laptop) PS C:\Users\praty\OneDrive\Desktop\DGA_ISRO> python src\scripts\06_create_split.py
train 21000
val 4500
test 4500
(.venv-laptop) PS C:\Users\praty\OneDrive\Desktop\DGA_ISRO> python src\scripts\07_cpu_sanity_check.py
Sanity check running on: cpu
epoch 0: train_loss=0.6932 val_loss=0.6769 val_f1=0.6671 val_auc=0.6650
epoch 1: train_loss=0.6781 val_loss=0.6638 val_f1=0.6882 val_auc=0.7265
epoch 2: train_loss=0.6660 val_loss=0.6515 val_f1=0.7036 val_auc=0.7537
epoch 3: train_loss=0.6545 val_loss=0.6397 val_f1=0.7669 val_auc=0.7780
epoch 4: train_loss=0.6431 val_loss=0.6281 val_f1=0.7820 val_auc=0.7937
epoch 5: train_loss=0.6321 val_loss=0.6167 val_f1=0.7804 val_auc=0.8036
epoch 6: train_loss=0.6220 val_loss=0.6056 val_f1=0.7658 val_auc=0.8071
epoch 7: train_loss=0.6118 val_loss=0.5948 val_f1=0.7574 val_auc=0.8071
epoch 8: train_loss=0.6014 val_loss=0.5843 val_f1=0.7482 val_auc=0.8080
epoch 9: train_loss=0.5914 val_loss=0.5742 val_f1=0.7428 val_auc=0.8097
epoch 10: train_loss=0.5820 val_loss=0.5642 val_f1=0.7440 val_auc=0.8133
epoch 11: train_loss=0.5729 val_loss=0.5544 val_f1=0.7502 val_auc=0.8182
epoch 12: train_loss=0.5634 val_loss=0.5446 val_f1=0.7581 val_auc=0.8235
epoch 13: train_loss=0.5536 val_loss=0.5348 val_f1=0.7693 val_auc=0.8299
epoch 14: train_loss=0.5427 val_loss=0.5250 val_f1=0.7761 val_auc=0.8364
epoch 15: train_loss=0.5338 val_loss=0.5151 val_f1=0.7846 val_auc=0.8433
epoch 16: train_loss=0.5243 val_loss=0.5049 val_f1=0.7919 val_auc=0.8503
epoch 17: train_loss=0.5136 val_loss=0.4945 val_f1=0.7974 val_auc=0.8577
epoch 18: train_loss=0.5036 val_loss=0.4837 val_f1=0.8032 val_auc=0.8659
epoch 19: train_loss=0.4927 val_loss=0.4727 val_f1=0.8079 val_auc=0.8739
CPU sanity check complete. (.venv-laptop) PS
.venv-laptop) PS C:\Users\praty\OneDrive\Desktop\DGA_ISRO> dir models\checkpoints
>> type results\logs\train_log.csv


    Directory: C:\Users\praty\OneDrive\Desktop\DGA_ISRO\models\checkpoints


Mode                 LastWriteTime         Length Name                                                                                        
----                 -------------         ------ ----                                                                                        
-a---l        22-07-2026     02:12        1264715 best_model.pt                                                                               
-a---l        22-07-2026     02:13        1264715 last_model.pt                                                                               
epoch,train_loss,val_loss,val_f1,val_auc
0,5.594637870788574,0.9265369176864624,0.461489898989899,0.6577523950617283
1,3.488377332687378,3.0771634578704834,0.3520336605890603,0.6013296790123457
2,3.924752950668335,2.45995831489563,0.40158782666225606,0.6289886419753086
3,3.3859846591949463,1.335814356803894,0.5197255574614065,0.6949123950617284
4,2.790149450302124,1.3847920894622803,0.65,0.681241975308642
5,2.766901731491089,1.756177544593811,0.6518431831480398,0.6764572839506172
6,2.770115613937378,1.2061374187469482,0.6429136975455265,0.6859872592592593
7,2.3651833534240723,1.2128721475601196,0.5489977728285078,0.7109199012345679
8,2.0198380947113037,1.5909498929977417,0.5048888888888889,0.6982975802469136
9,2.007983684539795,1.5987643003463745,0.5,0.7001029135802469


4) Why log1p before standardizing specifically for fanin: a handful of shared IPs/nameservers/registrars/ASNs likely have very high fan-in (popular shared infrastructure) while most have fan-in near 1 — a classic heavy-tailed distribution. log1p compresses that range before standardization, which directly addresses the abnormally high starting loss (~5.6 instead of ~0.69) you saw before.
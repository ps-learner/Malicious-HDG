import ijson
import pandas as pd
from pathlib import Path


def parse_file(path, label, sample_size):
    domain_rows, dns_rows, whois_rows, asn_rows = [], [], [], []

    with open(path, "rb") as f:
        for i, r in enumerate(ijson.items(f, "item")):
            if i >= sample_size:
                break

            domain = (r.get("domain_name") or "").lower().strip()
            if not domain:
                continue

            dns = r.get("dns") or {}
            rdap = r.get("rdap") or {}
            ip_data = r.get("ip_data") or []

            a_records = dns.get("A") or []
            aaaa_records = dns.get("AAAA") or []

            raw_ns = dns.get("NS") or []
            ns_records = []

            if isinstance(raw_ns, list):
                for ns in raw_ns:
                    if isinstance(ns, dict):
                        target = ns.get("target")
                        if target:
                            ns_records.append(target)
                    elif isinstance(ns, str):
                        if ns.strip():
                            ns_records.append(ns.strip())

            elif isinstance(raw_ns, dict):
                target = raw_ns.get("target")
                if target:
                    ns_records.append(target)

            elif isinstance(raw_ns, str):
                if raw_ns.strip():
                    ns_records.append(raw_ns.strip())

            domain_rows.append({
                "domain": domain,
                "label": label,            # your ML label: 'malicious' or 'benign'
                "raw_label": r.get("label"),
                "raw_category": r.get("category"),
                "evaluated_on": r.get("evaluated_on"),
            })

            dns_rows.append({
                "domain": domain,
                "a_records": a_records,
                "aaaa_records": aaaa_records,
                "ns_records": ns_records,
                "nxdomain": (len(a_records) == 0 and len(aaaa_records) == 0),
            })

            whois_rows.append({
                "domain": domain,
                "registrar": rdap.get("handle"),
                "registration_date": rdap.get("registration_date"),
            })

            for ip_entry in ip_data:
                if not isinstance(ip_entry, dict):
                    continue
                asn_info = ip_entry.get("asn") or {}
                asn_rows.append({
                    "ip": ip_entry.get("ip"),
                    "asn": asn_info.get("autonomous_system_number"),
                    "asn_org": asn_info.get("autonomous_system_organization"),
                })

    return domain_rows, dns_rows, whois_rows, asn_rows


SAMPLE_MALICIOUS = 5000
SAMPLE_BENIGN = 5000

mal = parse_file("data_raw/zenodo/malware.json", "malicious", SAMPLE_MALICIOUS)
ben = parse_file("data_raw/zenodo/benign_umbrella.json", "benign", SAMPLE_BENIGN)

Path("data_processed/enriched").mkdir(parents=True, exist_ok=True)

for name, mal_rows, ben_rows in zip(["domains", "dns", "whois", "asn"], mal, ben):
    df = pd.DataFrame(mal_rows + ben_rows)
    if name == "asn":
        df = df.dropna(subset=["ip"]).drop_duplicates(subset="ip")
    df.to_csv(f"data_processed/enriched/{name}.csv", index=False)
    print(name, "->", len(df), "rows")
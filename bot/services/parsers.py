import re
from bs4 import BeautifulSoup

def parse_characteristics(text: str) -> dict:
    if not text:
        return {}
    out = {}
    pat = re.compile(r'\s*([^:\n]+?)\s*:\s*(.+)$')
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = pat.match(line)
        if m:
            k, v = m.group(1).strip(), m.group(2).strip()
            out[k] = [x.strip() for x in v.split(";")] if ";" in v else [v]
        else:
            out[line] = [""]
    return out

def normalize_characteristics(parsed: dict) -> dict:
    return {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}

def dict_to_str(d: dict) -> str:
    lines = []
    for k, v in d.items():
        vs = "; ".join(v) if isinstance(v, list) else str(v)
        lines.append(f"{k}: {vs}")
    return "\n".join(lines)

def parse_product_parameters(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    out = {}
    for tbl in soup.find_all("table", class_="product-params__table"):
        grp = tbl.caption.get_text(strip=True) if tbl.caption else ""
        for tr in tbl.find_all("tr"):
            th, td = tr.find("th"), tr.find("td")
            if th and td:
                k = th.get_text(" ", strip=True)
                v = td.get_text(" ", strip=True)
                out[f"{grp}.{k}" if grp else k] = v
    return out

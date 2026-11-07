#!/usr/bin/env python3
"""stats.py - tarjetas de actividad de GitHub como SVG propios (solo biblioteca estándar).

Sustituye servicios compartidos (github-readme-stats, etc.) que fallan o se
agotan: aquí los SVG viven en tu repositorio y se muestran mientras GitHub
muestre tu repositorio.

    python scripts/stats.py --user NAREN2608 --out assets

Genera <out>/activity.svg (actividad + lenguajes, una sola imagen) usando solo datos públicos:
  - API REST de GitHub: repos, estrellas, bytes por lenguaje (sin forks).
  - Página pública de contribuciones: suma de los últimos 12 meses.
Si algo falla, termina con error SIN sobrescribir los SVG existentes.

Opciones de prueba: --save-data datos.json guarda lo recogido; --data datos.json
renderiza desde ese archivo sin consultar la red.
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import time
import urllib.request

API = "https://api.github.com"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,'DejaVu Sans Mono',monospace"
C = dict(win="#0E0C1C", border="#2C2756", panel2="#1A1740", white="#F5F3FF", gray="#92909F",
         cyan="#22D3EE", violet="#A78BFA", purple="#8B5CF6")
PALETTE = ["#8B5CF6", "#22D3EE", "#A78BFA", "#34D399", "#F0ABFC", "#FBBF24", "#92909F"]


def http(url, token=None, tries=4):
    headers = {"User-Agent": "profile-stats", "Accept": "application/vnd.github+json"}
    if token and url.startswith(API):
        headers["Authorization"] = f"Bearer {token}"
    for n in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
                return r.read().decode("utf-8")
        except Exception:
            if n == tries - 1:
                raise
            time.sleep(2 * (n + 1))


def collect(user, token):
    u = json.loads(http(f"{API}/users/{user}", token))
    repos, page = [], 1
    while True:
        chunk = json.loads(http(f"{API}/users/{user}/repos?per_page=100&type=owner&page={page}", token))
        repos += chunk
        if len(chunk) < 100:
            break
        page += 1
    langs = {}
    for r in repos:
        if r.get("fork"):
            continue
        for name, n in json.loads(http(f"{API}/repos/{user}/{r['name']}/languages", token)).items():
            langs[name] = langs.get(name, 0) + n
    page_html = http(f"https://github.com/users/{user}/contributions")
    m = re.search(r"([\d.,]+)\s+contributions?\s+in\s+the\s+last\s+year", page_html)
    days = re.findall(r"(\d+) contributions? on ", page_html)
    return {
        "public_repos": u["public_repos"],
        "followers": u["followers"],
        "since": int(u["created_at"][:4]),
        "stars": sum(r.get("stargazers_count", 0) for r in repos if not r.get("fork")),
        "contributions": int(re.sub(r"\D", "", m.group(1))) if m else (sum(map(int, days)) if days else None),
        "langs": langs,
        "updated": dt.date.today().isoformat(),
    }


def esc(s):
    return html.escape(str(s), quote=True)


def head(w, h, title, desc, pid="g"):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
            f'aria-label="{esc(title)}"><title>{esc(title)}</title><desc>{esc(desc)}</desc>'
            f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="14" fill="{C["win"]}" stroke="{C["border"]}" stroke-width="2"/>'
            f'<path d="M16 2H{w-16}" stroke="url(#{pid})" stroke-width="3.5" stroke-linecap="round"/>'
            f'<defs><linearGradient id="{pid}" x1="0" x2="1"><stop offset="0" stop-color="{C["purple"]}"/>'
            f'<stop offset="1" stop-color="{C["cyan"]}"/></linearGradient></defs>')


def t(x, y, s, size, fill, weight=400, anchor="start", extra=""):
    return (f'<text x="{x}" y="{y}" fill="{fill}" font-family="{MONO}" font-size="{size}" '
            f'font-weight="{weight}" text-anchor="{anchor}"{extra}>{esc(s)}</text>')


def fmt(n):
    return "-" if n is None else f"{n:,}".replace(",", ".")


def stats_svg(d, pid="ga"):
    w, h = 508, 250
    tiles = [("Repos públicos", fmt(d["public_repos"])), ("Contribuciones/año", fmt(d["contributions"])),
             ("Estrellas recibidas", fmt(d["stars"])), ("En GitHub desde", fmt(d["since"]) if d["since"] else "-")]
    o = [head(w, h, "Actividad en GitHub",
              "; ".join(f"{a}: {b}" for a, b in tiles), pid), t(24, 38, "ACTIVIDAD", 14, C["cyan"], 800, extra=' letter-spacing="1.2"'),
         f'<path d="M1 52H{w-1}" stroke="{C["border"]}" stroke-width="1.5"/>']
    for i, (label, val) in enumerate(tiles):
        x = 24 + (i % 2) * 238
        y = 70 + (i // 2) * 76
        o.append(f'<rect x="{x}" y="{y}" width="222" height="64" rx="8" fill="{C["panel2"]}" stroke="{C["border"]}"/>')
        o.append(t(x + 16, y + 34, val, 28, C["white"], 800))
        o.append(t(x + 16, y + 55, label, 14, C["gray"]))
    o.append(t(24, h - 14, f"datos públicos · actualizado {d['updated']}", 12.5, C["gray"]))
    return "".join(o) + "</svg>"


def langs_svg(d, pid="gb"):
    w, h = 508, 250
    langs = sorted(d["langs"].items(), key=lambda kv: -kv[1])
    total = sum(v for _, v in langs) or 1
    top = langs[:6]
    rest = sum(v for _, v in langs[6:])
    if rest:
        top.append(("Otros", rest))
    o = [head(w, h, "Lenguajes más usados", "; ".join(f"{k}: {v/total*100:.1f}%" for k, v in top), pid),
         t(24, 38, "LENGUAJES", 14, C["cyan"], 800, extra=' letter-spacing="1.2"'),
         t(w - 24, 38, "repos públicos, sin forks", 13, C["gray"], anchor="end"),
         f'<path d="M1 52H{w-1}" stroke="{C["border"]}" stroke-width="1.5"/>']
    if not langs:
        o.append(t(24, 130, "Se genera en la primera ejecución del flujo", 16, C["gray"]))
        return "".join(o) + "</svg>"
    bx, bw = 24, w - 48
    o.append(f'<clipPath id="c"><rect x="{bx}" y="72" width="{bw}" height="14" rx="7"/></clipPath><g clip-path="url(#c)">')
    x = bx
    for i, (k, v) in enumerate(top):
        seg = bw * v / total
        o.append(f'<rect x="{x:.1f}" y="72" width="{seg:.1f}" height="14" fill="{PALETTE[i]}"/>')
        x += seg
    o.append("</g>")
    for i, (k, v) in enumerate(top):
        col, row = i % 2, i // 2
        x, y = 24 + col * 238, 118 + row * 30
        o.append(f'<circle cx="{x + 6}" cy="{y - 5}" r="5.5" fill="{PALETTE[i]}"/>')
        o.append(t(x + 20, y, k, 15, C["white"]))
        o.append(t(x + 222, y, f"{v/total*100:.1f}%", 14, C["gray"], anchor="end"))
    o.append(t(24, h - 14, f"actualizado {d['updated']}", 12.5, C["gray"]))
    return "".join(o) + "</svg>"


def activity_svg(d):
    """Las dos tarjetas en una sola imagen: se escalan juntas y nunca se parten en dos líneas."""
    a, b = stats_svg(d), langs_svg(d)
    tag = '<svg xmlns="http://www.w3.org/2000/svg"'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1040 250" width="1040" height="250" role="img" '
            f'aria-label="Actividad en GitHub y lenguajes más usados">'
            f'<title>Actividad en GitHub y lenguajes más usados</title>'
            + a.replace(tag, '<svg x="0" y="0"', 1) + b.replace(tag, '<svg x="532" y="0"', 1) + "</svg>")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="NAREN2608")
    ap.add_argument("--out", default="assets")
    ap.add_argument("--data", help="renderizar desde un JSON en vez de consultar la red")
    ap.add_argument("--save-data", help="guardar los datos recogidos")
    a = ap.parse_args()
    try:
        d = json.load(open(a.data, encoding="utf-8")) if a.data else collect(a.user, os.environ.get("GITHUB_TOKEN"))
    except Exception as e:  # no tocar los SVG existentes si falla la recogida
        print(f"error recogiendo datos: {e}", file=sys.stderr)
        return 1
    if a.save_data:
        json.dump(d, open(a.save_data, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    os.makedirs(a.out, exist_ok=True)
    for name, fn in (("activity.svg", activity_svg),):
        with open(os.path.join(a.out, name), "w", encoding="utf-8") as f:
            f.write(fn(d))
        print("escrito", os.path.join(a.out, name))
    return 0


if __name__ == "__main__":
    sys.exit(main())

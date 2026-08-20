#!/usr/bin/env python3
"""Build: merge static/index.html + config.js + app.js + style.css → build/index.html"""
import re, os

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, "static")
BUILD = os.path.join(HERE, "build")

def read(path):
    with open(os.path.join(BASE, path), encoding="utf-8") as f:
        return f.read()

html = read("index.html")
css = read("style.css")
js = read("app.js")
cfg = read("config.js")

# Replace <link rel="stylesheet" href="style.css"> with inline <style>
html = re.sub(
    r'<link\s+[^>]*href="style\.css"[^>]*>',
    lambda m: f'<style>\n{css}\n</style>',
    html
)

# Replace <script src="config.js"></script> with inline (must stay BEFORE app.js)
html = re.sub(
    r'<script src="config\.js"></script>',
    lambda m: f'<script>\n{cfg}\n</script>',
    html
)

# Replace <script src="app.js"></script> with inline
html = re.sub(
    r'<script src="app\.js"></script>',
    lambda m: f'<script>\n{js}\n</script>',
    html
)

os.makedirs(BUILD, exist_ok=True)
out = os.path.join(BUILD, "index.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)

size = os.path.getsize(out)
print(f"[OK] Built {out} ({size:,} bytes = {size/1024:.0f} KB)")

import os
import glob
import re

html_files = glob.glob(os.path.join(os.path.dirname(__file__), '*.html'))

for file in html_files:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Replace nav button gradient
    content = re.sub(
        r'style="background:linear-gradient\(135deg,#E85D04,#7C3AED\);color:#fff;font-weight:700;padding:6px 14px;border-radius:6px;display:flex;align-items:center;gap:5px;"',
        'style="background:var(--bg2);color:var(--dark);font-weight:700;padding:6px 14px;border-radius:6px;display:flex;align-items:center;gap:5px;border:1px solid var(--border);"',
        content
    )
    # 2. Replace FREE tag gradient inside nav button
    content = re.sub(
        r'style="background:rgba\(255,255,255,0\.25\);font-size:10px;padding:1px 6px;border-radius:10px;font-weight:800;"',
        'style="background:var(--accent-light);color:var(--accent-dark);font-size:10px;padding:1px 6px;border-radius:4px;font-weight:800;"',
        content
    )
    # 3. Replace fill="#fff" inside nav button SVG
    content = re.sub(
        r'<svg width="13" height="13" fill="#fff" viewBox="0 0 24 24">',
        '<svg width="13" height="13" fill="var(--dark)" viewBox="0 0 24 24">',
        content
    )

    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)

print(f"Replaced gradients in {len(html_files)} files.")

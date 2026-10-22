import os, re

for root, dirs, files in os.walk('apps/api/app'):
    for f in files:
        if f.endswith('.py'):
            p = os.path.join(root, f)
            with open(p, 'r', encoding='utf-8', errors='ignore') as fl:
                text = fl.read()
                matches = re.findall(r'@(?:router|app)\.(get|post|put|delete)\(\s*["\']([^"\']+)["\']', text)
                for m, r in matches:
                    if 'observation' in r.lower() or 'pilot' in r.lower():
                        print(f"{p}: {m.upper()} {r}")

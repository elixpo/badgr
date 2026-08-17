import os
import re

for root, dirs, files in os.walk("apps"):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            with open(path, "r") as f:
                content = f.read()

            orig = content
            content = re.sub(r"widgets\.draw_header\(d,\s*(.+?)\)", r"self.title = \1", content)
            content = re.sub(r"widgets\.draw_hint\(d,\s*(.+?)\)", r"self.hint = \1", content)

            if content != orig:
                with open(path, "w") as f:
                    f.write(content)
                print(f"Fixed {path}")

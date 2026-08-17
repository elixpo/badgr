import os
import re

for root, dirs, files in os.walk("apps"):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            with open(path, "r") as f:
                content = f.read()

            def replace_hint(match):
                full_str = match.group(1)
                parts = re.split(r"\s{2,}", full_str)
                tuples = []
                for p in parts:
                    if "=" in p:
                        k, v = p.split("=", 1)
                        tuples.append(f'("{k}", "{v}")')
                    else:
                        tuples.append(f'("", "{p}")')

                list_str = "[" + ", ".join(tuples) + "]"
                return f"self.hints = {list_str}"

            new_content = re.sub(r'self\.hint\s*=\s*"(.*?)"', replace_hint, content)

            if new_content != content:
                with open(path, "w") as f:
                    f.write(new_content)
                print(f"Fixed {path}")

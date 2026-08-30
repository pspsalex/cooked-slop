# python __extract.py > out.mm
# Manually fix broken ingredients
import html
import re
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString


def extract_formatted_text(cell):
    parts = []

    for node in cell.descendants:
        if isinstance(node, NavigableString):
            # Check if this text node sits inside a <pre> element
            is_pre = any(parent.name == "pre" for parent in node.parents)

            if is_pre:
                parts.append(str(node))
            else:
                # Collapse source HTML line wraps and extra spaces into a single space
                parts.append(re.sub(r"\s+", " ", str(node)))

        elif node.name == "br":
            # Preserve intentional HTML line breaks
            parts.append("\n")
        elif node.name == "p":
            parts.append("\n\n")

    # Reassemble, unescape HTML entities, and normalize non-breaking spaces
    full_text = "".join(parts)
    return html.unescape(full_text).replace("\xa0", " ").strip()


def process_directory(root_folder="."):
    root = Path(root_folder)

    # .rglob("*.html") recursively traverses all subdirectories
    for file_path in root.rglob("*.htm"):
        try:
            with open(
                file_path, "r", encoding="utf-8", errors="ignore"
            ) as file:
                soup = BeautifulSoup(file, "html.parser")
                cells = soup.select("table tr td table tr td")

                if cells:
                    print(f"=== {file_path} ===")
                    for cell in cells:
                        print(extract_formatted_text(cell))
                        print()
        except Exception as err:
            print(f"Error processing {file_path}: {err}")


# Run starting from current directory
if __name__ == "__main__":
    process_directory(".")

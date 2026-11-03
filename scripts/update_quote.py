import json, random, re, pathlib

root = pathlib.Path(__file__).resolve().parent.parent
quotes = json.loads((root / "quotes.json").read_text(encoding="utf-8"))
q = random.choice(quotes)

block = (
    "<!--QUOTE_START-->\n"
    f"> *\"{q['text']}\"*\n"
    f"> — **{q['author']}**\n"
    "<!--QUOTE_END-->"
)

readme = root / "README.md"
text = readme.read_text(encoding="utf-8")
new = re.sub(r"<!--QUOTE_START-->.*?<!--QUOTE_END-->", lambda m: block, text, flags=re.S)
readme.write_text(new, encoding="utf-8")

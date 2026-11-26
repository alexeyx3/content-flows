"""Offline, pinned spaCy worker. Input/output are JSON; no service/API calls."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/refresh-semantics.json"


def source_hash() -> str:
    paths = [CONFIG, Path(__file__), ROOT / "scripts/refresh_semantics.py",
             ROOT / "scripts/md_to_gdoc.py", ROOT / "tools/semantics/runtime-lock.txt"]
    return hashlib.sha256(b"\0".join(p.read_bytes() for p in paths)).hexdigest()


def annotate(texts: list[str], language: str) -> tuple[list[list[dict]], dict]:
    """Cache exact normalized inputs; load the NLP model only for cache misses."""
    config = json.loads(CONFIG.read_text())
    if language not in config["models"]:
        raise ValueError(f"unsupported morphology language: {language}")
    identity = {"sources_sha256": source_hash(), "language": language,
                "spacy": config["spacy_version"], "model": config["models"][language],
                "model_version": config["model_version"]}
    prefix = json.dumps(identity, sort_keys=True)
    cache = ROOT / "var/semantics/lemmas.sqlite3"
    cache.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(cache, timeout=30) as db:
        db.execute("CREATE TABLE IF NOT EXISTS annotations (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        keys = {t: hashlib.sha256((prefix + '\0' + t).encode()).hexdigest() for t in dict.fromkeys(texts)}
        found = {t: json.loads(row[0]) for t, key in keys.items()
                 if (row := db.execute("SELECT value FROM annotations WHERE key=?", (key,)).fetchone())}
        missing = [t for t in keys if t not in found]
        if missing:
            python = ROOT / ".venv-semantics/bin/python"
            if not python.is_file():
                raise ValueError("local morphology runtime missing: run sh tools/semantics/setup.sh")
            env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", VECLIB_MAXIMUM_THREADS="1")
            result = subprocess.run([str(python), str(Path(__file__)), "worker"],
                                    input=json.dumps({"language": language, "texts": missing}, ensure_ascii=False),
                                    capture_output=True, text=True, env=env, timeout=300)
            if result.returncode:
                raise ValueError("local morphology failed: " + result.stderr[-1500:])
            data = json.loads(result.stdout)
            if data["engine"] != {k: identity[k] for k in ("spacy", "model", "model_version")}:
                raise ValueError("morphology runtime/model version differs from pinned configuration")
            for text, tokens in zip(missing, data["tokens"], strict=True):
                found[text] = tokens
                db.execute("INSERT OR REPLACE INTO annotations VALUES (?,?)", (keys[text], json.dumps(tokens, ensure_ascii=False)))
        return [found[t] for t in texts], identity


def worker() -> None:
    import spacy
    request = json.load(sys.stdin)
    config = json.loads(CONFIG.read_text())
    model = config["models"][request["language"]]
    nlp = spacy.load(model, disable=["parser", "ner"])
    if "sentencizer" not in nlp.pipe_names:
        nlp.add_pipe("sentencizer", first=True)
    names = re.compile(r"(?<!\w)(?:" + "|".join(map(re.escape, config["protected_names"])) + r")(?!\w)", re.I)
    output = []
    for doc in nlp.pipe(request["texts"], batch_size=32):
        protected = [m.span() for m in names.finditer(doc.text)]
        tokens, segment, previous_end = [], 0, 0
        for token in doc:
            if token.is_space or token.is_punct:
                continue
            gap = doc.text[previous_end:token.idx]
            # Keep hyphenated forms comparable; never bridge sentences/clauses.
            if re.search(r"[.!?,;:\n]", gap):
                segment += 1
            frozen = token.like_num or any(a <= token.idx < b for a, b in protected)
            tokens.append({"text": token.text, "lemma": (token.text if frozen else token.lemma_).casefold(),
                           "start": token.idx, "end": token.idx + len(token.text),
                           "segment": segment, "stop": bool(token.is_stop)})
            previous_end = token.idx + len(token.text)
        output.append(tokens)
    json.dump({"engine": {"spacy": spacy.__version__, "model": model, "model_version": nlp.meta["version"]},
               "tokens": output}, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    worker()

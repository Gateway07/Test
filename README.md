# RAG Chunking CLI

A simple, single-threaded CLI to parse insurance rules documents (DOCX/RTF), chunk them for embeddings, vectorize with Ollama, and retrieve relevant chunks from Chroma DB.

## Highlights

- Parse `.docx` with `python-docx` and `.rtf` with `striprtf`
- Chunk with `langchain-text-splitters` (token-based default)
- Embed via `langchain_community` (Ollama) with a configurable model (e.g., `nomic-embed-text`)
- Vector store powered by `langchain_chroma` (Chroma) with persistence
- Two commands: `-p` pipeline (ingest), `-q` query (retrieve)
- Configurable via `config.yaml`, environment variables, and CLI flags (flags override config/env)

## Project Structure

```
RAG_Chunking/
├─ main.py                 # CLI entry point
├─ reading.py              # DocumentReader for DOCX/RTF
├─ processing.py           # Chunker + Vectorizer (Chroma)
├─ config.yaml             # Defaults for env/pipeline/query
├─ requirements.txt        # Python dependencies
├─ docs/
│  ├─ Specification.md     # CLI specification
│  └─ Task.md              # Task and requirements
└─ chroma/                 # Default Chroma persistence dir (created at runtime)
```

## Installation

1) Create and activate a virtual environment (Windows):

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

2) Install dependencies:

```powershell
pip install -r requirements.txt
```

3) Ensure [Ollama](https://ollama.com) is running and the chosen embedding model is available locally (e.g., `nomic-embed-text`).

## Configuration

Defaults are provided in `config.yaml`. The `environment` section seeds environment variables (only if not already set). CLI flags override both environment and config.

Example `config.yaml` keys:

```yaml
environment:
  OLLAMA_HOST: http://127.0.0.1:11434
  CHROMA_PERSIST_DIR: '.\\chroma'
  CHROMA_COLLECTION: rag-docs
  MODEL: nomic-embed-text

pipeline:
  chunk_size: 512
  overlap_size: 128
  separators: '\n\n,\n,\.\s,\s'
  file_glob: "**/*.{docx,rtf}"
  print_stats: false

query:
  k: 8
  include_scores: false
```

Environment keys used by the app:
- `MODEL` (preferred) or `EMBED_MODEL`: embedding model name (Ollama)
- `CHROMA_COLLECTION`: Chroma collection name
- `CHROMA_PERSIST_DIR`: Chroma persistence directory
- `OLLAMA_HOST`: Ollama host URL

## Usage

Show help:

```powershell
python main.py --help
```

Run pipeline (parse -> chunk -> vectorize):

```powershell
python main.py -p --input_dir .\2025-09-20_insurance_rules --print_stats --verbose
```

Query top-K chunks:

```powershell
python main.py -q "договор внутреннего страхования" --k 8 --include_scores
```

Select a different model/collection/persist dir via env or flags:

```powershell
$env:MODEL = "nomic-embed-text"
$env:CHROMA_COLLECTION = "insurance-rules"
$env:CHROMA_PERSIST_DIR = ".\chroma"
python main.py -p --input_dir .\2025-09-20_insurance_rules
```

## How It Works

- `reading.py`:
  - `DocumentReader` recursively scans the input directory and parses `.docx`/`.rtf`, returning plain text + metadata.
- `processing.py`:
  - `Chunker` splits text with `TokenTextSplitter` (default) or `RecursiveCharacterTextSplitter` using ordered separators.
  - `Vectorizer` embeds chunks with Ollama and indexes them into Chroma. Progress logs show batch upsert status.
- `main.py`:
  - `-p` runs the full ingestion pipeline.
  - `-q` embeds the query and retrieves top-K results with optional scores.

## Notes

- Single-threaded by design (per task assumptions).
- By default, chunking is token-based with `chunk_size=512`, `overlap_size=128`. Adjust for your model’s context window.
- `.docx` and `.rtf` supported by default; `file_glob` is `**/*.{docx,rtf}`.

## Troubleshooting

- No documents found:
  - Ensure `--input_dir` is correct and contains `.docx`/`.rtf` files.
  - Run with `--verbose` to see discovery logs.
- Embedding errors:
  - Confirm Ollama is running and `MODEL` is downloaded/available.
  - Check `OLLAMA_HOST` in `config.yaml` or env vars.
- Chroma persistence:
  - Ensure `CHROMA_PERSIST_DIR` is writable.

## Roadmap

- Add tests and CI
- Optional multiprocessing for parsing when allowed
- Configurable similarity display (distance vs. similarity)
- More robust DOCX/RTF structure extraction (headings, tables)

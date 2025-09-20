# RAG Chunking CLI Specification

This document defines the command-line interface (CLI) for a terminal application that supports document parsing, chunking, and vectorization for a RAG system, and provides a query capability to retrieve the most relevant chunks. The specification is derived from the functional requirements in `Task.md`.

## Scope

- Input documents: MS Word `.docx`, `*.rtf` files (Russian language).
- Parsing: Simple, linear structure parsing suitable for typical insurance policy rule documents.
- Embeddings: Ollama platform models.
- Vector store: Chroma DB.
- CLI runs on Windows 10, Python environment.
- Minimal error handling is acceptable per assumptions; CLI should still validate required arguments and report actionable errors.

## High-Level Architecture

- Document Reader: Recursive directory traversal with file filters to collect `.docx` and `.rtf` files.
- Parser: DOCX/RTF text extractor producing plain text with basic structural markers (e.g., paragraphs, headings if present) using `python-docx` (for `.docx`) and `striprtf` (for `.rtf`).
- Text Splitter: Configurable chunking (chunk size, overlap, separators) tuned to the selected embedding model context using `langchain-text-splitters` (`RecursiveCharacterTextSplitter`).
- Embedder: Uses Ollama embedding model via `langchain_community.embeddings` (e.g., `OllamaEmbeddings`); produces vectors for each chunk with metadata (document name, positions, path, chunk index, etc.).
- Vector Store: Chroma collection for persistence and retrieval via `langchain_chroma` integration.
- Query: Embeds the input question and retrieves top-K chunks, printing metadata and optional scores.

## Conventions

- All CLI commands are invoked via `python main.py`.
- Short commands are flags `-p` for pipeline and `-q` for query.
- Each command supports its own sub-parameters and `--help`.
- Paths accept absolute or relative Windows paths.

## Selected Defaults (from Task.md)

- Embedding model default: `FRIDA` (evilfreelancer/FRIDA) via Ollama.
- Chunking defaults (token-based): `--chunk_size 512`, `--overlap_size 128`.
- Retrieval default: `--k 8`.
- Parallel workers: not considered; implementation is single-threaded per assumptions.

## Required vs Optional Parameters

- Only two parameters are required:
  - For `-p` (pipeline): `--input_dir`.
  - For `-q` (query): a positional `query` string.
- All other flags across both commands are optional and have sensible defaults.

## Framework Choices and Rationale

- Parsing (`.docx`): Prefer `python-docx` for reliable extraction of paragraph-level text and basic structural elements in Word documents. It is widely used, actively maintained, and robust for linear document structures common in insurance rules.
- Parsing (`.rtf`): Use `striprtf` to convert RTF to plain text. It is lightweight, handles Cyrillic well in practice, and fits the minimal-structure requirement. Alternative: `pyrtf-ng` if richer structure is ever needed.
- Chunking: Use `langchain-text-splitters` (specifically `RecursiveCharacterTextSplitter`). It allows:
  - Ordered separators (e.g., double newline, newline, sentence breaks, whitespace) to respect boundaries.
  - Configurable `chunk_size` and `chunk_overlap`.
  - Good behavior on multilingual text including Russian, with simple character-based heuristics.

- Embeddings and Vector Store Integration:
  - Use `langchain_community.embeddings` for Ollama-backed embeddings for simpler wiring and consistent interfaces.
  - Use `langchain_chroma` to interface with Chroma DB as the primary vector store implementation.

These choices balance simplicity, performance, and quality given the assumption of linear document structure and minimal error handling.

## Commands

### 1) Pipeline Command `-p`

Runs the full pipeline for documents parsing, chunking, and vectorizing.

Usage:

```powershell
python main.py -p --help
python main.py -p --input_dir "D:\\data\\docs" --chunk_size 512 --overlap_size 128 --separators "\n\n,\n,\.\s,\s" --model "FRIDA" --collection "insurance-rules" --persist_dir ".\\chroma" --rebuild
```

Required:
- `--input_dir <str>`: Root directory to recursively scan for `.docx`/`.rtf` files.

Optional:
- `--chunk_size <int>`: Target tokens per chunk. Default: `512`.
- `--overlap_size <int>`: Token overlap between adjacent chunks. Default: `128`.
- `--separators <str>`: Comma-separated list of regex or literal separators to prioritize splitting (in order). Default: "\n\n,\n,\.\s,\s".
- `--model <str>`: Ollama embedding model name. Default: `"FRIDA"`.
- `--collection <str>`: Chroma collection name. Default: `"rag-docs"`.
- `--persist_dir <str>`: Directory where the Chroma DB persists. Default: `.\\chroma`.
- `--rebuild`: If present, drops existing collection before re-ingesting.
- `--file_glob <str>`: Glob filter applied under `--input_dir` (e.g., `**/*.docx`). Default: `**/*.{docx,rtf}`.
- `--max_files <int>`: Optional limit for number of files to process (for quick tests). Default: no limit.
- `--print_stats`: If present, prints summary stats (files, chunks, avg chunk length, time).

Behavior:
- Recursively scans `--input_dir` for files matching `--file_glob`.
- Extracts plain text from `.docx`/`.rtf` files (skip encrypted/corrupt files with warning).
- Splits text using the specified `--separators`, `--chunk_size` (tokens), and `--overlap_size` (tokens).
- Embeds each chunk with `--model` via Ollama and writes vectors into Chroma `--collection` at `--persist_dir`.
- Stores metadata per chunk: `source_path`, `filename`, `chunk_index`, `char_start`, `char_end`, `total_chars`, `doc_hash` (optional), `ingested_at`.
- If `--rebuild`, drops the collection before ingestion.
- If `--print_stats`, prints totals and timings.

Output:
- Console progress and summary per file and totals if `--print_stats`.
- Chroma persisted collection on disk at `--persist_dir`.

Exit Codes:
- `0` on success.
- `2` if input validation fails (e.g., missing `--input_dir`).
- `3` if embedding or vector store operation fails.

### 2) Query Command `-q`

Embeds a query and retrieves top-K chunks from the Chroma collection.

Usage:

```powershell
python main.py -q "договор внутреннего страхования" --k 8 --collection "insurance-rules" --persist_dir ".\\chroma" --model "FRIDA" --include_scores
```

Required:
- Positional `query <str>`: The user question or search phrase.

Optional:
- `--k <int>`: Number of top chunks to retrieve. Default: `8`.
- `--collection <str>`: Chroma collection name. Default: `"rag-docs"`.
- `--persist_dir <str>`: Directory where the Chroma DB persists. Default: `.\chroma`.
- `--model <str>`: Ollama embedding model name. Default: same as used in ingestion.
- `--score_threshold <float>`: Optional minimal similarity score to include results.
- `--include_scores`: If present, prints similarity scores alongside results.
- `--limit_per_doc <int>`: Optional cap on results from the same source document.
- `--filters <JSON>`: Optional metadata filter applied at retrieval time (e.g., by filename or path).

Behavior:
- Embeds the `query` using `--model` via Ollama.
- Retrieves `--k` nearest chunks from `--collection` in `--persist_dir`.
- Prints a compact report including document metadata and optionally similarity scores.
- If `--limit_per_doc` is provided, enforces the cap when formatting results for display.
- If `--filters` is provided, applies to metadata fields (e.g., `{ "filename": "policy.docx" }`).

Output Format (Console):
- Rank, score (if `--include_scores`), source filename, path (basename), chunk index, and a short text preview (first ~200 chars).
- Example:

```
[1] score=0.842 | file=Правила_страхования.docx | chunk=12 | pos=10234-11055
     "... текст чанка ..."
[2] score=0.833 | file=Правила_страхования.docx | chunk=3 | pos=1870-2600
     "... текст чанка ..."
```

Exit Codes:
- `0` on success.
- `2` if required args are missing or collection not found.
- `3` if embedding or retrieval fails.

## Configuration

- Environment variables (optional):
  - `OLLAMA_HOST`: Ollama server base URL, e.g., `http://127.0.0.1:11434`.
  - `CHROMA_PERSIST_DIR`: Default persist directory for Chroma.
  - `CHROMA_COLLECTION`: Default collection name.
  - `EMBED_MODEL`: Default Ollama embedding model name. Default: `FRIDA`.
- Config file: `config.yaml` to supply defaults for the above and chunking parameters.
- CLI flags always override environment/config defaults.

## Dependencies and Runtime Assumptions

- Python 3.10+ recommended.
- Ollama running locally with the selected embedding model pulled.
- Chroma DB Python package available; persistent client points to `--persist_dir`.
- DOCX parsing via a robust open-source library (e.g., `python-docx` or `docx2python`).
- RTF parsing via `striprtf`.
- Chunking via `langchain-text-splitters`.
- Embeddings and utilities via `langchain_community` (e.g., `OllamaEmbeddings`).
- Chroma integration via `langchain_chroma`.

## Logging and Error Handling

- Console logging with INFO level by default; DEBUG enabled with `--verbose` (global flag).
- Warnings for unreadable files; continue processing remaining files.
- Fatal errors (e.g., failed connection to Ollama/Chroma) terminate with a non-zero exit code and a clear message.

## Global Flags

These flags can be provided before the sub-command flags and affect behavior globally:

- `--verbose`: Enable detailed logging (DEBUG).
- `--no_color`: Disable ANSI colors in output.

Examples:

```powershell
python main.py --verbose -p --input_dir D:\docs
python main.py --no_color -q "страховая сумма" --k 6
```

## Data Model (Metadata Fields)

- `id`: Unique chunk ID (e.g., hash of `source_path + chunk_index + content`).
- `source_path`: Full path to the source file.
- `filename`: Basename of the source file.
- `chunk_index`: Zero-based index of the chunk within the document.
- `char_start`, `char_end`: Character offsets within the original document text.
- `total_chars`: Total character length of the original document text.
- `ingested_at`: ISO timestamp of ingestion.
- `doc_hash` (optional): Hash of the original document content for change detection.

## Performance Considerations

- Implementation is single-threaded per assumptions; parallel job workers are not considered.
- Batch embedding requests when supported by the Ollama model API.
- Avoid high `--overlap_size` unless needed to maintain context.

## Examples

Help:

```powershell
python main.py --help
python main.py -p --help
python main.py -q --help
```

Pipeline:

```powershell
python main.py -p --input_dir D:\\Projects\\InsuranceDocs --chunk_size 512 --overlap_size 128 --model FRIDA --collection insurance-rules --persist_dir .\\chroma --print_stats
```

Query:

```powershell
python main.py -q "договор внутреннего страхования" --k 8 --include_scores --model FRIDA --collection insurance-rules --persist_dir .\\chroma
```

## Acceptance Criteria

- `-p` runs end-to-end ingestion over a directory tree of `.docx` files and persists vectors in Chroma.
- `-q` returns top-K chunks with their metadata and optional scores.
- Each command exposes `--help` showing its specific options as listed here.
- Defaults are sensible and allow a minimal successful run with only the required arguments.

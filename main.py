"""
CLI entry point for RAG Chunking app.

Commands:
- -p: Pipeline (parse -> chunk -> embed -> upsert to Chroma)
- -q: Query (retrieve top-k similar chunks)

Defaults are aligned with docs/Specification.md:
- Embedding model: FRIDA
- chunk_size: 512 tokens
- overlap_size: 128 tokens
- retrieval k: 8
- single-threaded
"""
import argparse
import json
import logging
import os
import sys
from typing import Dict, List, Tuple

import yaml  # PyYAML for config file loading

from reading import DocumentReader, ParsedDocument
from processing import Chunker, Vectorizer


DEFAULT_SEPARATORS = "\n\n,\n,\\.\\s,\\s"


def load_config(path: str = "config.yaml") -> Dict:
    """Load configuration YAML if present. Returns an empty dict if missing or invalid."""
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                # Apply environment defaults from config if not set
                env = data.get("environment", {}) or {}
                for k, v in env.items():
                    os.environ.setdefault(str(k), str(v))
                return data
    except Exception as exc:  # pragma: no cover
        logging.getLogger(__name__).warning(f"Failed to read config file '{path}': {exc}")
    return {}


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def parse_separators(s: str) -> List[str]:
    # Keep raw separators as a list in order
    return [part for part in (p.strip() for p in s.split(",")) if part]


def _resolve_persist_dir(args: argparse.Namespace) -> str:
    if getattr(args, "CHROMA_PERSIST_DIR", None):
        return args.CHROMA_PERSIST_DIR
    if getattr(args, "persist_dir", None):
        return args.persist_dir
    return os.getenv("CHROMA_PERSIST_DIR", ".\\chroma")


def command_pipeline(args: argparse.Namespace) -> int:
    logger = logging.getLogger("pipeline")

    # Validate required input_dir
    if not args.input_dir:
        logger.error("--input_dir is required for -p (pipeline)")
        return 2

    # Read documents
    reader = DocumentReader(logger=logging.getLogger("reader"))
    docs: List[ParsedDocument] = reader.read_documents(
        input_dir=args.input_dir,
        file_glob=args.file_glob,
        max_files=args.max_files,
    )

    if not docs:
        logger.warning("No documents found for ingestion.")

    # Prepare chunker (token-based by default)
    separators = parse_separators(args.separators)
    chunker = Chunker(
        chunk_size=args.chunk_size,
        overlap_size=args.overlap_size,
        separators=separators,
        use_token_splitter=True,
        logger=logging.getLogger("chunker"),
    )

    # Build texts with metadata
    to_chunk: List[Tuple[str, dict]] = []
    for pd in docs:
        meta = {
            "source_path": pd.source_path,
            "filename": pd.filename,
            "doc_hash": pd.doc_hash,
        }
        to_chunk.append((pd.text, meta))

    chunks = chunker.chunk(to_chunk)

    # Vectorize
    persist_dir = _resolve_persist_dir(args)
    vect = Vectorizer(
        model=args.model,
        collection=args.collection,
        persist_dir=persist_dir,
        logger=logging.getLogger("vectorizer"),
    )

    if args.rebuild:
        vect.rebuild_collection()

    vect.upsert(chunks)

    if args.print_stats:
        total_chars = sum(pd.total_chars for pd in docs)
        logger.info(
            "Stats: files=%d chunks=%d avg_chunk_len=%.1f total_chars=%d",
            len(docs),
            len(chunks),
            (sum(len(c.page_content) for c in chunks) / max(len(chunks), 1)),
            total_chars,
        )

    return 0


def command_query(args: argparse.Namespace) -> int:
    logger = logging.getLogger("query")
    if not args.q:
        logger.error("-q requires a query string, e.g., -q \"<your question>\"")
        return 2

    persist_dir = _resolve_persist_dir(args)
    vect = Vectorizer(
        model=args.model or os.getenv("EMBED_MODEL", "FRIDA"),
        collection=args.collection,
        persist_dir=persist_dir,
        logger=logging.getLogger("vectorizer"),
    )

    results = vect.similarity_search(args.q, k=args.k, include_scores=args.include_scores)

    # Optional metadata filters (simple equality filter)
    filters: Dict[str, str] = {}
    if args.filters:
        try:
            filters = json.loads(args.filters)
            if not isinstance(filters, dict):
                raise ValueError("filters must be a JSON object")
        except Exception as exc:
            logger.error(f"Invalid JSON for --filters: {exc}")
            return 2

    # Apply limit per doc and filters while formatting
    seen_per_doc: Dict[str, int] = {}
    displayed = 0
    for rank, (doc, score) in enumerate(results, start=1):
        meta = doc.metadata or {}
        if filters:
            if not all(str(meta.get(k, "")) == str(v) for k, v in filters.items()):
                continue
        fname = meta.get("filename", "<unknown>")
        if args.limit_per_doc is not None:
            count = seen_per_doc.get(fname, 0)
            if count >= args.limit_per_doc:
                continue
            seen_per_doc[fname] = count + 1

        preview = doc.page_content[:200].replace("\n", " ")
        if args.include_scores:
            print(f"[{rank}] score={score:.3f} | file={fname} | chunk={meta.get('chunk_index','?')} | pos={meta.get('char_start','?')}-{meta.get('char_end','?')}")
        else:
            print(f"[{rank}] file={fname} | chunk={meta.get('chunk_index','?')} | pos={meta.get('char_start','?')}-{meta.get('char_end','?')}")
        print(f"     \"{preview}\"")
        displayed += 1
        if displayed >= args.k:
            break

    return 0


def build_parser() -> argparse.ArgumentParser:
    # Load config first to use as defaults
    cfg = load_config()
    pipeline_cfg = cfg.get("pipeline", {}) if isinstance(cfg, dict) else {}
    query_cfg = cfg.get("query", {}) if isinstance(cfg, dict) else {}

    parser = argparse.ArgumentParser(description="RAG Chunking CLI")

    # Global flags
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--no_color", action="store_true", help="Disable ANSI colors in output (no-op)")

    # Mode flags
    parser.add_argument("-p", action="store_true", help="Run pipeline: parse + chunk + vectorize")
    parser.add_argument("-q", metavar="query", type=str, help="Query string to search", nargs="?")

    # Pipeline options
    parser.add_argument("--input_dir", type=str, help="Input directory to scan for documents (.docx, .rtf)")
    parser.add_argument("--chunk_size", type=int, default=pipeline_cfg.get("chunk_size", 512), help="Target tokens per chunk (default: 512)")
    parser.add_argument("--overlap_size", type=int, default=pipeline_cfg.get("overlap_size", 128), help="Token overlap between chunks (default: 128)")
    parser.add_argument("--separators", type=str, default=pipeline_cfg.get("separators", DEFAULT_SEPARATORS), help="Comma-separated ordered separators")
    # Single source of truth for model/collection/persist_dir from environment (config.environment)
    parser.add_argument("--model", type=str, default=os.getenv("MODEL", os.getenv("EMBED_MODEL", "FRIDA")), help="Ollama embedding model (env: MODEL)")
    parser.add_argument("--collection", type=str, default=os.getenv("CHROMA_COLLECTION", "rag-docs"), help="Chroma collection name (env: CHROMA_COLLECTION)")
    # Prefer explicit env-style flag; keep --persist_dir as backward-compatible alias
    parser.add_argument("--CHROMA_PERSIST_DIR", type=str, default=os.getenv("CHROMA_PERSIST_DIR", ".\\chroma"), help="Chroma persist directory (env/flag: CHROMA_PERSIST_DIR)")
    parser.add_argument("--persist_dir", type=str, default=None, help="[DEPRECATED] Use --CHROMA_PERSIST_DIR instead")
    parser.add_argument("--rebuild", action="store_true", default=bool(pipeline_cfg.get("rebuild", False)), help="Drop existing collection before ingesting")
    parser.add_argument("--file_glob", type=str, default=pipeline_cfg.get("file_glob", "**/*.{docx,rtf}"), help="Glob filter under input_dir")
    parser.add_argument("--max_files", type=int, default=pipeline_cfg.get("max_files", None), help="Limit number of files to process")
    parser.add_argument("--print_stats", action="store_true", default=bool(pipeline_cfg.get("print_stats", False)), help="Print ingestion statistics")

    # Query options
    parser.add_argument("--k", type=int, default=query_cfg.get("k", 8), help="Top-K chunks to retrieve (default: 8)")
    parser.add_argument("--include_scores", action="store_true", default=bool(query_cfg.get("include_scores", False)), help="Include similarity scores in output")
    parser.add_argument("--limit_per_doc", type=int, default=query_cfg.get("limit_per_doc", None), help="Limit results per document")
    parser.add_argument("--filters", type=str, default=query_cfg.get("filters", None), help="Metadata filter as JSON object")

    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    setup_logging(args.verbose)

    # Ensure exactly one of -p or -q is used
    run_pipeline = bool(args.p)
    run_query = args.q is not None
    if run_pipeline == run_query:
        print("Use exactly one of: -p or -q <query>")
        return 2

    if run_pipeline:
        return command_pipeline(args)
    return command_query(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

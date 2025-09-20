# Goal

Необходимо реализовать один из этапов RAG системы, где происходит чанкирование базы знаний для последующего
использования при поиске в векторной БД.
В качестве базы знаний будут предоставлены MS Word документы с общедоступными правилами для страхования одной из
страховых компаний РБ.
Таким образом, главная цель состоит в разработке функционала для хранения чанков (определить размер,
контекст и т.д.) с последующим формированием наиболее эффективного ответа пользователю в RAG системах.

Требуется:

- Реализовать чанкирования входных документов.
- Разработать удобный способ тестирования полученных чанков.

# Assumptions

- Input documents are in MS Word (docx, rtf) format on Russian.
- Simple MS Word docx parsing with linear documents structure.
- Ollama is platform to run embedding model.
- Vector search retrieval is based on Chroma as Vector DB.
- Open-source frameworks is primary resource to select implementation basis.
- Parallel job workers for loading and vectorizing data is not considered.
- To test chunking should be developed appropriate CLI.
- No unit-tests, minimal error handling.

# Functional requirements

### 1. Documents parsing and chunking

- Determine the best Python framework for parsing and chunking MS Word files.
- Determine appropriate chunk size, overlap size, separators based on embedding Ollama model specification (context
  size) and
  structure of input documents.
- Develop recursive dirs document reader with text splitter and chunking.

#### Open-source framework choice for parsing and chunking

- Parsing `.docx`: `python-docx`
  - Widely used and actively maintained.
  - Reliable paragraph-level extraction and basic structural markers for linear Word documents typical to insurance rules.
  - Simple API and minimal dependencies, suitable for Windows 10 environments.
- Parsing `.rtf`: `striprtf`
  - Lightweight RTF-to-text conversion that handles Cyrillic text well in practice.
  - Fits the assumption of simple/linear text without requiring heavy formatting support.
  - Alternative (if richer structure is ever needed): `pyrtf-ng`.
- Chunking: `langchain-text-splitters` (`RecursiveCharacterTextSplitter`)
  - Honors an ordered list of separators (e.g., `\n\n`, `\n`, sentence boundaries, whitespace) to avoid breaking semantic units.
  - Exposes configurable `chunk_size` and `chunk_overlap` to match embedding model context constraints.
  - Proven in multilingual scenarios, practical for Russian text and contract-style prose.

### 3. Documents vectorizing

- Determine the best embedding Ollama model for Russian language and insurance business area.
- Implement documents chunks vectorizing with saving them in Chroma DB including meta-info (positions, name of
  documents).

#### Embedding Model Selection (Language and Document Structure)

- Prioritize multilingual embedding models available in Ollama that handle Russian text well and general-domain prose
  typical of insurance policies.
- Selection criteria:
    - Multilingual capability with good Russian coverage.
    - Sufficient input context length to accommodate intended `chunk_size`.
    - Stable similarity performance on paragraph-level retrieval.
- Candidate examples (available in the local Ollama install):
    - `FRIDA` (evilfreelancer/FRIDA) - Specifically finetuned for Russian/English text. Max context window ~512 tokens.
    - `bge-m3` (multilingual, strong general retrieval). Maximum input length of 8192 tokens.
    - `nomic-embed-text` (good baseline; validate RU performance on your corpus). May not capture complex semantics as
      finely.

Default in this task remains `FRIDA` as a first baseline.

#### Parameter Guidance Based on Embedding Model Context

- `--chunk_size`:
    - Goal: Keep each chunk within the model’s maximum input tokens to avoid truncation during embedding.
    - Russian words are longer on average; this range avoids fragmenting sentences while staying far from the point
      where unrelated subtopics creep in.
    - Empirically gives better retrieval precision/recall in contract-style corpora large context than tiny (≤100) token
      windows.
    - Default chunk size is 512 tokens.

- `--overlap_size`:
    - Purpose: Preserve context across chunk boundaries for topics spanning sentences/paragraphs.
    - Reduce overlap for very long chunks to control total tokens and ingestion cost.
    - Default overlap size is 128 tokens.
  
- `--separators`:
    - Ordered list to respect structure: `"\n\n,\n,\.\s,\s"`.
    - For Russian, sentence boundary `\.\s` is a practical proxy; adjust if documents contain many abbreviations.

- Retrieval `--k`. Default is `8`. Higher values increase recall but may reduce precision and add noise.
  
### 4. Testing CLI

- Implement CLI for testing with the following commands:

Get help on available commands:

```powershell
python main.py --help
```

Available commands:

- `-p` - Run the full pipeline for docs parsing, chunking, vectorizing with its own sub parameters: --input_dir,
  --chunk-size, --overlap_size
- `-q` - Process question using specified parameters: --k (top K chunks)

Each command should have its own options. For example:

```powershell
python main.py -p --help
# Shows options like --input_dir, --chunk-size, --overlap_size

python main.py -q "договор внутреннего страхования" --k 4
# Retrive top K chunks and print found docs meta-info 
```



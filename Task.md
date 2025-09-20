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

- Input documents are in MS Word (docx) format on Russian.
- Simple MS Word docx parsing with linear documents structure.
- Ollama is platform to run embedding model.
- Vector search retrieval is based on Chroma as Vector DB.
- Open-source frameworks is primary resource to select implementation basis.
- To test chunking should be developed appropriate CLI.
- No unit-tests, minimal error handling.

# Functional requirements

### 1. Documents parsing and chunking

- Determine the best Python framework for parsing and chunking MS Word (docx) file.
- Determine appropriate chunk size, overlap size, separators based on embedding Ollama model specification (context size) and
  structure of input documents.
- Develop recursive dirs document reader with text splitter and chunking.

### 3. Documents vectorizing

- Determine the best embedding Ollama model for Russian language and insurance business area.
- Implement documents chunks vectorizing with saving them in Chroma DB including meta-info (positions, name of documents).

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


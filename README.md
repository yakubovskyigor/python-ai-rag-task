# Product Catalog Normalization & Hybrid Search

A small Python implementation of product catalog normalization, manufacturer data harvesting, SKU matching, and hybrid search.

The project was created as a solution for the recruitment task M1.

## Overview

The input data contains product records from several manufacturers in an inconsistent format.

The solution consists of three main stages:

1. Normalize the source catalog into a consistent schema.
2. Harvest additional product information from a manufacturer HTML snapshot and match it with the catalog.
3. Provide exact SKU search and multilingual semantic search with optional manufacturer/category filters.

The input dataset contains 218 catalog records after normalization.

---

## Project Structure

```text
python-ai-rag-task/
├── data/
│   ├── Data_katalog_probka.csv
│   ├── Data_producent_novagen_snapshot.html
│   └── normalized_catalog.csv
│
├── src/
│   ├── normalization.py
│   ├── harvester.py
│   └── hybrid_search.py
│
├── tests/
│   ├── test_normalization.py
│   └── test_hybrid_search.py
│
├── .flake8
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 1. Normalization

The source CSV contains inconsistent representations of the same product attributes.

The normalized schema contains:

```text
sku
name
manufacturer
category
package_raw
price
attributes
package_quantity
package_unit
currency
```

The harvester additionally enriches the catalog with:

```text
description
specs
```

### Category normalization

Different Polish and English category names are mapped to a common set of canonical categories.

For example:

```text
PCR - odczynniki
Odczynniki PCR
Odczynniki do PCR
        ↓
PCR reagents
```

Similarly, laboratory chemicals, plasticware, measuring equipment, and nucleic acid isolation categories are normalized.

Missing categories are preserved as missing values rather than being guessed.

### Package normalization

Different representations are converted into a quantity and unit:

```text
50 rxn
50 reactions
50 szt.
x50
50 test.
        ↓
quantity = 50
unit = pcs
```

Package values such as `50-pack` are represented separately as:

```text
quantity = 50
unit = package
```

The original representation is preserved in `package_raw`.

### Price normalization

Prices are converted to `Decimal`.

Examples of supported representations include:

```text
1955 PLN
1955 zl
1955,00
1955.00
```

The normalized currency is stored as:

```text
PLN
```

Missing prices remain missing.

---

## 2. Duplicate and Near-Duplicate Handling

Exact duplicate catalog numbers are grouped together.

For conflicting values, the implementation does not silently choose one value. If multiple non-null values exist for the same field, a conflict is raised.

Near-duplicate SKU candidates are detected using Levenshtein edit distance.

A candidate is treated as a possible SKU typo when:

- the manufacturer matches;
- the Levenshtein distance between the harvested SKU and catalog SKU is at most 1.

This allows the harvester to detect the provided typo:

```text
NO-103l6 → NO-10316
```

while avoiding false matches such as:

```text
NO-10500 → NO-10001
```

Near-duplicate catalog records are not automatically merged. They are reported as candidates for review because similar SKUs may represent valid product variants.

For the provided catalog, the detected near-duplicate candidates are:

```text
CH-10248  ↔  CH-10248A
PO-10093  ↔  PO-10093A
```

Both pairs have identical comparison fields, but they are kept as separate records because the `A` suffix may represent a valid product variant.

---

## 3. Product Data Harvester

The manufacturer snapshot is parsed using BeautifulSoup.

Each product card contains information such as:

```text
SKU
name
description
specifications
```

The harvester extracts all available product cards and then tries to match them against the normalized catalog.

### Matching strategy

The primary matching key is the catalog number.

Product names are not used as the primary matching key because names may differ between sources.

The matching process is:

```text
exact SKU
    ↓
SKU typo candidate
    ↓
unmatched
```

For SKU typo detection, the manufacturer must match and the Levenshtein distance between SKUs must be at most 1.

### SKU typo

The snapshot contains:

```text
NO-103l6
```

while the catalog contains:

```text
NO-10316
```

The `l` character is an obvious typo.

The matching logic detects this difference using Levenshtein edit distance:

```text
NO-103l6 → NO-10316
distance = 1
```

The record is therefore matched as:

```text
NO-103l6 → NO-10316
```

and marked as a `sku_typo` match.

### Products without a catalog match

Two products from the snapshot do not have a corresponding catalog entry:

```text
NO-10500
NO-99999
```

They are not automatically inserted into the catalog.

This is intentional: the snapshot may contain products outside the main catalog, and manual enrichment of such products is not required.

---

## 4. Hybrid Search

The search implementation combines deterministic SKU matching with semantic retrieval.

### Exact SKU search

If the query exactly matches a catalog SKU, the exact result takes priority.

Example:

```text
Query:
NO-10009

Result:
NO-10009
score = 1.0
match_type = exact_sku
```

This avoids using semantic similarity for a deterministic identifier lookup.

### Semantic search

Natural-language queries are processed using:

```text
sentence-transformers/
paraphrase-multilingual-MiniLM-L12-v2
```

The model supports multilingual semantic similarity, which is useful because the catalog contains Polish product names while queries may be written in English or Polish.

FAISS is used for vector similarity search.

For the current dataset of 218 products, an in-memory FAISS index is sufficient and keeps the implementation simple.

### Filters

The search supports:

```text
manufacturer
category
```

Filters are applied before semantic retrieval.

For example:

```text
products for isolating RNA from blood
--manufacturer "NovaGen Labs"
```

first restricts the catalog to NovaGen Labs products and then performs semantic search within that subset.

The search also works with Polish queries, for example:

```text
produkty do izolacji RNA z krwi
```

---

## 5. Scoring and Explanation

Every search result contains:

```text
score
match_type
reason
```

For exact SKU matches:

```text
score = 1.0
match_type = exact_sku
```

For semantic matches, the score is the similarity returned by the embedding search.

A short explanation is generated based on the semantic score.

For example:

```text
Strong semantic match with the user query.
```

or:

```text
Good semantic match with the user query.
```

Lower-scoring results are described as:

```text
Weaker semantic match; included among the top results.
```

---

## 6. Running the Project

Create and activate a virtual environment:

```bash
python -m venv .venv
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### Run normalization

```bash
python -m src.normalization
```

### Run the harvester

```bash
python -m src.harvester
```

The harvester processes the manufacturer HTML snapshot, performs SKU matching, reports unmatched products, and saves the enriched catalog to:

```text
data/normalized_catalog.csv
```

### Search by SKU

```bash
python src/hybrid_search.py NO-10009
```

### Semantic search

```bash
python src/hybrid_search.py "products for isolating RNA from blood"
```

### Semantic search with manufacturer filter

```bash
python src/hybrid_search.py "products for isolating RNA from blood" --manufacturer "NovaGen Labs"
```

### Semantic search with category filter

```bash
python src/hybrid_search.py "RNA isolation" --category "Nucleic Acid Isolation"
```

---

## 7. Tests

The project contains tests for normalization, duplicate handling, and hybrid search functionality.

Run all tests:

```bash
python -m pytest
```

The current test suite contains 11 tests covering:

- catalog normalization;
- exact duplicate merging;
- conflicting duplicate values;
- near-duplicate SKU detection;
- exact SKU matching;
- semantic search;
- manufacturer filtering;
- category filtering;
- multilingual semantic search;
- fallback to semantic search for an unknown SKU;
- exact SKU behavior with filters.

Expected result:

```text
11 passed
```

---

## 8. Design Decisions and Trade-offs

### Why not PostgreSQL or Qdrant?

The provided dataset contains only about 218 products.

For this scale, an in-memory pandas DataFrame combined with FAISS is sufficient and keeps the implementation lightweight.

For a production catalog with millions of products, I would move the normalized data to PostgreSQL and use pgvector or a dedicated vector database.

### Why not use an LLM for matching?

The current task can be solved deterministically for SKU matching and with embeddings for semantic retrieval.

Using an LLM for SKU matching would add unnecessary complexity and make deterministic identifier matching less reliable.

### Why exact SKU before semantic search?

SKU is a deterministic identifier. If it exists in the catalog, semantic similarity should not be allowed to return a different product.

Therefore, exact SKU matching takes priority over semantic retrieval.

### Why use Levenshtein distance for SKU typo detection?

SKU values are structured identifiers, so a small edit distance is more meaningful than general semantic similarity.

The provided typo differs from the catalog SKU by one character:

```text
NO-103l6
NO-10316
```

Using a maximum Levenshtein distance of 1 provides a simple and deterministic rule for the provided dataset while avoiding false matches such as:

```text
NO-10500
NO-10001
```

In a production system, this threshold would be calibrated using labeled historical matching data.

### What could be improved with more time?

For a larger production system I would consider:

- persistent vector storage;
- incremental embedding updates;
- database-backed filtering;
- a dedicated retrieval/reranking stage;
- better explanation generation based on matching fields;
- more extensive data-quality validation;
- monitoring of matching confidence and unmatched manufacturer records;
- an HTTP API instead of CLI-only access.

---

## Limitations

This implementation is intentionally small and focused on the requirements of the recruitment task.

The semantic index is built in memory during execution rather than persisted between runs.

The current scoring is based directly on embedding similarity for semantic results and a deterministic score of `1.0` for exact SKU matches.

SKU typo matching uses a deterministic Levenshtein distance threshold and is designed for the provided dataset.

The solution is designed for the provided dataset rather than for production-scale catalog volumes.
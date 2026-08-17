from pathlib import Path
import argparse

import faiss
import pandas as pd
from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/" "paraphrase-multilingual-MiniLM-L12-v2"


def load_catalog() -> pd.DataFrame:
    path = Path(__file__).parent.parent / "data" / "normalized_catalog.csv"

    return pd.read_csv(path)


def build_product_text(row: pd.Series) -> str:
    values = [
        row["name"],
        row["manufacturer"],
        row["category"],
        row["description"],
        row["specs"],
    ]

    return " ".join(str(value) for value in values if pd.notna(value))


def build_index(
    catalog: pd.DataFrame,
    model: SentenceTransformer,
):
    texts = [build_product_text(row) for _, row in catalog.iterrows()]

    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
    ).astype("float32")

    index = faiss.IndexFlatIP(embeddings.shape[1])

    index.add(embeddings)

    return index


def exact_sku_search(
    query: str,
    catalog: pd.DataFrame,
) -> pd.DataFrame:
    query = query.strip().casefold()

    matches = catalog[catalog["sku"].fillna("").str.casefold() == query].copy()

    return matches


def filter_catalog(
    catalog: pd.DataFrame,
    manufacturer: str | None = None,
    category: str | None = None,
) -> pd.DataFrame:
    result = catalog.copy()

    if manufacturer is not None:
        result = result[
            result["manufacturer"].fillna("").str.casefold() == manufacturer.casefold()
        ]

    if category is not None:
        result = result[
            result["category"].fillna("").str.casefold() == category.casefold()
        ]

    return result


def semantic_search(
    query: str,
    catalog: pd.DataFrame,
    model: SentenceTransformer,
    top_k: int = 5,
) -> pd.DataFrame:
    if catalog.empty:
        return catalog.copy()

    texts = [build_product_text(row) for _, row in catalog.iterrows()]

    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
    ).astype("float32")

    index = faiss.IndexFlatIP(embeddings.shape[1])

    index.add(embeddings)

    query_embedding = model.encode(
        [query],
        normalize_embeddings=True,
    ).astype("float32")

    scores, indices = index.search(
        query_embedding,
        min(top_k, len(catalog)),
    )

    results = catalog.iloc[indices[0]].copy()

    results["semantic_score"] = scores[0]

    return results


def build_exact_results(
    matches: pd.DataFrame,
) -> pd.DataFrame:
    if matches.empty:
        return matches

    results = matches.copy()

    results["score"] = 1.0
    results["match_type"] = "exact_sku"
    results["reason"] = "Exact catalog number match."

    return results


def build_semantic_results(
    results: pd.DataFrame,
) -> pd.DataFrame:
    if results.empty:
        return results

    results = results.copy()

    results["score"] = results["semantic_score"]

    def make_reason(score: float) -> str:
        if score >= 0.80:
            return "Strong semantic match with the " "user query."

        if score >= 0.65:
            return "Good semantic match with the " "user query."

        return "Weaker semantic match; included among " "the top results."

    results["reason"] = results["score"].apply(make_reason)

    results["match_type"] = "semantic"

    return results


def hybrid_search(
    query: str,
    catalog: pd.DataFrame,
    model: SentenceTransformer,
    manufacturer: str | None = None,
    category: str | None = None,
    top_k: int = 5,
) -> pd.DataFrame:

    # 1. Exact SKU match has priority.
    exact_matches = exact_sku_search(
        query,
        catalog,
    )

    if not exact_matches.empty:
        return build_exact_results(exact_matches)

    # 2. Apply filters before semantic retrieval.
    filtered_catalog = filter_catalog(
        catalog,
        manufacturer=manufacturer,
        category=category,
    )

    # 3. Semantic retrieval.
    semantic_results = semantic_search(
        query,
        filtered_catalog,
        model,
        top_k=top_k,
    )

    # 4. Add score and explanation.
    return build_semantic_results(semantic_results)


def parse_args():
    parser = argparse.ArgumentParser(description="Hybrid product catalog search")

    parser.add_argument(
        "query",
        help="Search query or catalog SKU",
    )

    parser.add_argument(
        "--manufacturer",
        help="Filter by manufacturer",
    )

    parser.add_argument(
        "--category",
        help="Filter by category",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of semantic results",
    )

    return parser.parse_args()


def print_results(
    results: pd.DataFrame,
):
    if results.empty:
        print("No results found.")
        return

    columns = [
        "sku",
        "name",
        "manufacturer",
        "category",
        "score",
        "match_type",
        "reason",
    ]

    available_columns = [column for column in columns if column in results.columns]

    print(results[available_columns].to_string(index=False))


if __name__ == "__main__":
    args = parse_args()

    catalog = load_catalog()

    print(f"Catalog size: {len(catalog)}")

    model = SentenceTransformer(MODEL_NAME)

    results = hybrid_search(
        query=args.query,
        catalog=catalog,
        model=model,
        manufacturer=args.manufacturer,
        category=args.category,
        top_k=args.top_k,
    )

    print(f"\nQuery: {args.query}")

    if args.manufacturer:
        print(f"Manufacturer filter: " f"{args.manufacturer}")

    if args.category:
        print(f"Category filter: " f"{args.category}")

    print("\nResults:")

    print_results(results)

from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

from src.normalization import normalize_catalog


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None

    return " ".join(value.split())


def load_html() -> BeautifulSoup:
    path = (
        Path(__file__).parent.parent / "data" / "Data_producent_novagen_snapshot.html"
    )

    with open(path, encoding="utf-8") as file:
        return BeautifulSoup(file, "html.parser")


def parse_product(product) -> dict:
    sku = product.get("data-sku")
    name = product.select_one(".product-name")
    description = product.select_one(".product-desc")
    specs = product.select(".specs li")

    return {
        "sku": sku,
        "name": clean_text(name.get_text(" ", strip=True)) if name else None,
        "description": (
            clean_text(description.get_text(" ", strip=True)) if description else None
        ),
        "specs": [clean_text(item.get_text(" ", strip=True)) for item in specs],
        "manufacturer": "NovaGen Labs",
    }


def harvest_products(soup) -> list[dict]:
    products = soup.select(".product-card")

    return [parse_product(product) for product in products]


def match_by_name(
    record: dict,
    catalog: pd.DataFrame,
) -> pd.DataFrame:
    return catalog[catalog["name"].str.casefold() == record["name"].casefold()]


def match_sku_typo(
    record: dict,
    catalog: pd.DataFrame,
) -> str | None:
    candidates = catalog[catalog["name"].str.casefold() == record["name"].casefold()]

    candidates = candidates[
        candidates["manufacturer"].str.casefold() == record["manufacturer"].casefold()
    ]

    best_match = None
    best_similarity = 0.0

    for _, row in candidates.iterrows():
        similarity = SequenceMatcher(
            None,
            record["sku"],
            row["sku"],
        ).ratio()

        if similarity > best_similarity:
            best_similarity = similarity
            best_match = row["sku"]

    return best_match


def match_product(
    record: dict,
    catalog: pd.DataFrame,
) -> dict:
    catalog_skus = set(catalog["sku"])

    # Exact SKU match
    if record["sku"] in catalog_skus:
        return {
            "harvested_sku": record["sku"],
            "catalog_sku": record["sku"],
            "match_type": "exact",
        }

    # SKU typo match
    typo_match = match_sku_typo(record, catalog)

    if typo_match:
        return {
            "harvested_sku": record["sku"],
            "catalog_sku": typo_match,
            "match_type": "sku_typo",
        }

    # No match
    return {
        "harvested_sku": record["sku"],
        "catalog_sku": None,
        "match_type": "unmatched",
    }


def enrich_catalog(
    catalog: pd.DataFrame,
    records: list[dict],
    matches: list[dict],
) -> pd.DataFrame:
    catalog = catalog.copy()

    html_by_catalog_sku = {
        match["catalog_sku"]: record
        for record, match in zip(records, matches)
        if match["catalog_sku"] is not None
    }

    catalog["description"] = catalog["sku"].map(
        lambda sku: (
            html_by_catalog_sku[sku]["description"]
            if sku in html_by_catalog_sku
            else None
        )
    )

    catalog["specs"] = catalog["sku"].map(
        lambda sku: (
            html_by_catalog_sku[sku]["specs"] if sku in html_by_catalog_sku else []
        )
    )

    return catalog


def get_unmatched_products(
    records: list[dict],
    matches: list[dict],
) -> list[dict]:
    return [
        record
        for record, match in zip(records, matches)
        if match["match_type"] == "unmatched"
    ]


if __name__ == "__main__":
    # Load and parse HTML
    soup = load_html()
    records = harvest_products(soup)

    print(f"Products harvested: {len(records)}")

    # Load and normalize catalog
    data_path = Path(__file__).parent.parent / "data" / "Data_katalog_probka.csv"

    catalog = pd.read_csv(data_path)
    catalog = normalize_catalog(catalog)

    print(f"Catalog products: {len(catalog)}")

    # Match harvested products with catalog
    matches = [match_product(record, catalog) for record in records]

    print("\nMatching results:")

    for match in matches:
        print(match)

    # Enrich catalog with HTML data
    enriched_catalog = enrich_catalog(
        catalog,
        records,
        matches,
    )

    # Find products that exist only in HTML
    unmatched_products = get_unmatched_products(
        records,
        matches,
    )

    print("\nUnmatched products:")

    for product in unmatched_products:
        print(
            product["sku"],
            product["name"],
        )

    # Save enriched catalog
    output_path = Path(__file__).parent.parent / "data" / "normalized_catalog.csv"

    enriched_catalog.to_csv(
        output_path,
        index=False,
    )

    print(f"\nSaved catalog: {output_path}")

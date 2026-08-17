from decimal import Decimal
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

CATEGORY_MAP = {
    "PCR reagents": "PCR reagents",
    "PCR - odczynniki": "PCR reagents",
    "Odczynniki PCR": "PCR reagents",
    "Odczynniki do PCR": "PCR reagents",
    "Chemia laboratoryjna": "Laboratory Chemicals",
    "Chemicals": "Laboratory Chemicals",
    "Odczynniki chemiczne": "Laboratory Chemicals",
    "Odczynniki": "Laboratory Chemicals",
    "Plastik laboratoryjny": "Laboratory Plasticware",
    "Plastiki lab.": "Laboratory Plasticware",
    "Laboratory Plasticware": "Laboratory Plasticware",
    "Measuring Equipment": "Measuring Equipment",
    "Pomiary": "Measuring Equipment",
    "Aparatura pomiarowa": "Measuring Equipment",
    "Sprzet pomiarowy": "Measuring Equipment",
    "Nucleic Acid Isolation": "Nucleic Acid Isolation",
    "Izolacja kwasow nukleinowych": "Nucleic Acid Isolation",
    "izolacja DNA/RNA": "Nucleic Acid Isolation",
    "Izolacja DNA": "Nucleic Acid Isolation",
    "Sprzet jednorazowy": "Disposable Equipment",
}

PCS_SUFFIXES = {
    "szt",
    "szt.",
    "rxn",
    "reactions",
    "test.",
}

PACKAGE_SUFFIXES = {
    "op",
    "pack",
}


def normalize_category(value: str | None) -> str | None:
    if pd.isna(value):
        return None

    value = value.strip()

    return CATEGORY_MAP.get(value)


def normalize_sku(value: str) -> str:
    return value.strip().upper()


def normalize_package(
    value: str | None,
) -> tuple[float | None, str | None]:
    if value is None or pd.isna(value):
        return None, None

    value = value.strip().lower()

    parts = value.split()

    if len(parts) == 2 and parts[1] in {"g", "kg", "ml", "l"}:
        return float(parts[0]), parts[1]

    if len(parts) == 2 and parts[1] in PCS_SUFFIXES:
        return float(parts[0]), "pcs"

    if value.endswith("szt"):
        quantity = value[:-3]
        return float(quantity), "pcs"

    if value.startswith("x"):
        return float(value[1:]), "pcs"

    if value.endswith("-pack"):
        quantity = value[:-5]
        return float(quantity), "package"

    if len(parts) == 2 and parts[1] in PACKAGE_SUFFIXES:
        return float(parts[0]), "package"

    if len(parts) == 2 and parts[1] == "-":
        return float(parts[0]), None

    if len(parts) == 1:
        return float(parts[0]), None

    return None, None


def normalize_price(
    value: str | None,
) -> Decimal | None:
    if pd.isna(value):
        return None

    value = value.strip().lower()
    value = value.replace("pln", "")
    value = value.replace("zl", "")
    value = value.strip()
    value = value.replace(",", ".")

    return Decimal(value)


def merge_value(values):
    non_null = values.dropna().unique()

    if len(non_null) == 0:
        return None

    if len(non_null) == 1:
        return non_null[0]

    raise ValueError(f"Conflicting values: {non_null}")


def merge_duplicates(
    df: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for sku, group in df.groupby("nr_katalogowy"):
        row = {"nr_katalogowy": sku}

        for column in df.columns:
            if column == "nr_katalogowy":
                continue

            row[column] = merge_value(group[column])

        rows.append(row)

    return pd.DataFrame(rows)


COMPARISON_FIELDS = [
    "nazwa",
    "producent",
    "kategoria",
    "opakowanie",
    "cena",
    "atrybuty_dodatkowe",
]


def compare_sku_candidates(
    df: pd.DataFrame,
    sku1: str,
    sku2: str,
) -> dict[str, bool]:
    row1 = df[df["nr_katalogowy"] == sku1].iloc[0]

    row2 = df[df["nr_katalogowy"] == sku2].iloc[0]

    return {field: row1[field] == row2[field] for field in COMPARISON_FIELDS}


def count_matching_fields(
    comparison: dict[str, bool],
) -> int:
    return sum(comparison.values())


def find_near_duplicate_skus(
    df: pd.DataFrame,
) -> list[dict]:
    skus = df["nr_katalogowy"].tolist()
    candidates = []

    for i, sku1 in enumerate(skus):
        for sku2 in skus[i + 1 :]:
            similarity = SequenceMatcher(
                None,
                sku1,
                sku2,
            ).ratio()

            if similarity < 0.9 or sku1 == sku2:
                continue

            comparison = compare_sku_candidates(
                df,
                sku1,
                sku2,
            )

            matching_fields = count_matching_fields(comparison)

            if matching_fields == len(COMPARISON_FIELDS):
                candidates.append(
                    {
                        "sku1": sku1,
                        "sku2": sku2,
                        "similarity": similarity,
                        "matching_fields": matching_fields,
                    }
                )

    return candidates


def normalize_catalog(
    df: pd.DataFrame,
) -> pd.DataFrame:
    df = merge_duplicates(df)

    df = df.rename(
        columns={
            "nr_katalogowy": "sku",
            "nazwa": "name",
            "producent": "manufacturer",
            "kategoria": "category",
            "opakowanie": "package_raw",
            "cena": "price",
            "atrybuty_dodatkowe": "attributes",
        }
    )

    df["sku"] = df["sku"].apply(normalize_sku)

    df["category"] = df["category"].apply(normalize_category)

    df["package_quantity"] = df["package_raw"].apply(
        lambda value: normalize_package(value)[0]
    )

    df["package_unit"] = df["package_raw"].apply(
        lambda value: normalize_package(value)[1]
    )

    df["price"] = df["price"].apply(normalize_price)

    df["currency"] = df["price"].apply(
        lambda value: ("PLN" if pd.notna(value) else None)
    )

    df["attributes"] = df["attributes"].where(
        df["attributes"].notna(),
        None,
    )

    return df


if __name__ == "__main__":
    data_path = Path(__file__).parent.parent / "data" / "Data_katalog_probka.csv"

    df = pd.read_csv(data_path)

    normalized_df = normalize_catalog(df)

    print(normalized_df.isna().sum())

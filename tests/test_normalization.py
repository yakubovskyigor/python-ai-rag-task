from src.normalization import merge_duplicates, merge_value, normalize_catalog
import pandas as pd
import pytest
from decimal import Decimal


def test_merge_duplicates():
    df = pd.DataFrame(
        [
            {
                "nazwa": "Product A",
                "nr_katalogowy": "TEST-001",
                "producent": "Test",
                "kategoria": "PCR reagents",
                "opakowanie": "50 rxn",
                "cena": "1000 PLN",
                "atrybuty_dodatkowe": None,
            },
            {
                "nazwa": "Product A",
                "nr_katalogowy": "TEST-001",
                "producent": "Test",
                "kategoria": "PCR reagents",
                "opakowanie": "50 rxn",
                "cena": "1000 PLN",
                "atrybuty_dodatkowe": "store at 4C",
            },
        ]
    )

    result = merge_duplicates(df)

    assert len(result) == 1
    assert result.iloc[0]["nr_katalogowy"] == "TEST-001"
    assert result.iloc[0]["atrybuty_dodatkowe"] == "store at 4C"


def test_merge_value_raises_on_conflict():
    values = pd.Series(["store at 4C", "store at -20C"])

    with pytest.raises(ValueError):
        merge_value(values)


def test_normalize_catalog():
    df = pd.DataFrame(
        [
            {
                "nazwa": "Product A",
                "nr_katalogowy": "TEST-001",
                "producent": "Test",
                "kategoria": "Odczynniki PCR",
                "opakowanie": "50 rxn",
                "cena": "1990,00",
                "atrybuty_dodatkowe": None,
            },
            {
                "nazwa": "Product A",
                "nr_katalogowy": "TEST-001",
                "producent": "Test",
                "kategoria": "Odczynniki PCR",
                "opakowanie": "50 rxn",
                "cena": "1990,00",
                "atrybuty_dodatkowe": "store at 4C",
            },
        ]
    )

    result = normalize_catalog(df)

    assert len(result) == 1
    assert result.iloc[0]["sku"] == "TEST-001"
    assert result.iloc[0]["category"] == "PCR reagents"
    assert result.iloc[0]["package_quantity"] == 50
    assert result.iloc[0]["package_unit"] == "pcs"
    assert result.iloc[0]["price"] == Decimal("1990.00")
    assert result.iloc[0]["currency"] == "PLN"
    assert result.iloc[0]["attributes"] == "store at 4C"

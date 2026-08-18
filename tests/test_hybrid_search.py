import pytest

from src.hybrid_search import (
    MODEL_NAME,
    hybrid_search,
    load_catalog,
)
from sentence_transformers import SentenceTransformer


@pytest.fixture
def catalog():
    return load_catalog()


@pytest.fixture
def model():
    return SentenceTransformer(MODEL_NAME)


def test_exact_sku_match(catalog, model):
    results = hybrid_search(
        query="NO-10009",
        catalog=catalog,
        model=model,
    )

    assert len(results) == 1
    assert results.iloc[0]["sku"] == "NO-10009"
    assert results.iloc[0]["match_type"] == "exact_sku"
    assert results.iloc[0]["score"] == 1.0


def test_semantic_search(catalog, model):
    results = hybrid_search(
        query="products for isolating RNA from blood",
        catalog=catalog,
        model=model,
        top_k=5,
    )

    assert not results.empty
    assert len(results) <= 5
    assert results.iloc[0]["sku"] == "ME-10017"
    assert results.iloc[0]["match_type"] == "semantic"
    assert results.iloc[0]["score"] > 0.8


def test_manufacturer_filter(catalog, model):
    results = hybrid_search(
        query="products for isolating RNA from blood",
        catalog=catalog,
        model=model,
        manufacturer="NovaGen Labs",
        top_k=5,
    )

    assert not results.empty
    assert all(results["manufacturer"].str.casefold() == "novagen labs")
    assert results.iloc[0]["sku"] == "NO-10009"


def test_unknown_sku_uses_semantic_search(catalog, model):
    results = hybrid_search(
        query="NO-999999",
        catalog=catalog,
        model=model,
        top_k=5,
    )

    assert not results.empty
    assert all(results["match_type"] == "semantic")


def test_exact_sku_respects_manufacturer_filter(catalog, model):
    results = hybrid_search(
        query="NO-10009",
        catalog=catalog,
        model=model,
        manufacturer="BioPrime",
        top_k=5,
    )

    assert not results.empty
    assert all(results["manufacturer"].str.casefold() == "bioprime")
    assert all(results["match_type"] == "semantic")


def test_category_filter(catalog, model):
    results = hybrid_search(
        query="RNA isolation",
        catalog=catalog,
        model=model,
        category="Nucleic Acid Isolation",
        top_k=5,
    )

    assert not results.empty
    assert all(results["category"].str.casefold() == "nucleic acid isolation")
    assert all(results["match_type"] == "semantic")


def test_polish_semantic_search(catalog, model):
    results = hybrid_search(
        query="produkty do izolacji RNA z krwi",
        catalog=catalog,
        model=model,
        top_k=5,
    )

    assert not results.empty
    assert results.iloc[0]["sku"] == "ME-10017"
    assert results.iloc[0]["match_type"] == "semantic"
    assert results.iloc[0]["score"] > 0.8

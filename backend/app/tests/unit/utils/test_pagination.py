"""Tests for :mod:`app.utils.pagination`."""

from __future__ import annotations

from app.utils.pagination import Page, PageParams, empty_page, validate_page_params


class TestPageParams:
    def test_offset_calculation(self) -> None:
        params = PageParams(page=3, page_size=25)
        assert params.offset == 50

    def test_limit_clamps_to_max(self) -> None:
        params = PageParams(page=1, page_size=200)
        assert params.limit == 100


class TestPage:
    def test_total_pages(self) -> None:
        page = Page(items=[1, 2, 3], total_records=137, page=1, page_size=25)
        assert page.total_pages == 6

    def test_has_next(self) -> None:
        page: Page[int] = Page(items=[], total_records=50, page=1, page_size=25)
        assert page.has_next is True

    def test_no_next_on_last_page(self) -> None:
        page: Page[int] = Page(items=[], total_records=50, page=2, page_size=25)
        assert page.has_next is False

    def test_metadata_structure(self) -> None:
        page = Page(items=[1, 2], total_records=10, page=1, page_size=25)
        meta = page.metadata
        assert meta == {
            "page": 1,
            "page_size": 25,
            "total_records": 10,
            "total_pages": 1,
        }


class TestValidatePageParams:
    def test_defaults(self) -> None:
        params = validate_page_params()
        assert params.page == 1
        assert params.page_size == 25

    def test_clamps_negative_page(self) -> None:
        params = validate_page_params(page=-1)
        assert params.page == 1

    def test_clamps_large_page_size(self) -> None:
        params = validate_page_params(page_size=500)
        assert params.page_size == 100


class TestEmptyPage:
    def test_returns_empty_page(self) -> None:
        page = empty_page()
        assert page.items == []
        assert page.total_records == 0
        assert page.has_next is False

"""Модульні тести клієнта API Приват24 (T009)."""
from datetime import date
import pytest
from src.bond_collector.client import Privat24Client, Privat24APIError


@pytest.mark.unit
class TestPrivat24Client:
    """Тестування методів взаємодії з API, retry та оновлення сесії."""

    def test_init_session_success(self, monkeypatch):
        client = Privat24Client()

        class MockResp:
            status_code = 200

            def json(self):
                return {"xref": "1234567890abcdef" * 4, "base_url": "api/p24/pub/"}

            def raise_for_status(self):
                pass

        monkeypatch.setattr(client.session, "post", lambda *args, **kwargs: MockResp())
        xref, base_url = client.init_session()
        assert client.xref == xref
        assert client.base_url == "api/p24/pub/"

    def test_auto_reinit_on_session_expired(self, monkeypatch):
        client = Privat24Client()
        client.xref = "expired_token"
        client.base_url = "api/p24/pub/"

        call_count = {"init": 0, "bargaining": 0}

        def mock_post(url, *args, **kwargs):
            class MockResp:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    if "init" in url:
                        call_count["init"] += 1
                        return {"xref": "new_valid_token" * 4, "base_url": "api/p24/pub/"}
                    call_count["bargaining"] += 1
                    if call_count["bargaining"] == 1:
                        # Симуляція помилки застарілої сесії (код 95 або повідомлення)
                        return {"code": 95, "message": "session_was_expired"}
                    # Другий виклик повертає успішний результат
                    return [{"isin": "UA4000227185", "name": "Тест", "currency": "UAH", "term": "2027-05-26"}]

            return MockResp()

        monkeypatch.setattr(client.session, "post", mock_post)

        bonds = client.get_raw_bonds()
        assert len(bonds) == 1
        assert call_count["init"] == 1
        assert call_count["bargaining"] == 2

    def test_limits_handling_zero_count(self, monkeypatch):
        client = Privat24Client()
        client.xref = "valid_xref"
        client.base_url = "api/p24/pub/"

        class MockResp:
            status_code = 200

            def json(self):
                return {"isin": "UA4000227185", "count": 0, "active": False}

            def raise_for_status(self):
                pass

        monkeypatch.setattr(client.session, "get", lambda *args, **kwargs: MockResp())

        limits = client.get_limits("UA4000227185")
        assert limits["count"] == 0
        assert limits["active"] is False

    def test_graceful_degradation_on_limits_error(self, monkeypatch):
        client = Privat24Client()
        client.xref = "valid_xref"
        client.base_url = "api/p24/pub/"

        class MockResp:
            status_code = 500

            def raise_for_status(self):
                raise Exception("Server 500")

            def json(self):
                return {}

        monkeypatch.setattr(client.session, "get", lambda *args, **kwargs: MockResp())

        # При помилці limits клієнт повинен повернути дефолтний словник безпечно
        limits = client.get_limits("UA4000227185")
        assert limits["count"] == 0
        assert limits["active"] is False

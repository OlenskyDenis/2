"""Контрактні тести для перевірки структури даних публічного API Приват24 (T008)."""
import pytest
from src.bond_collector.client import Privat24Client


@pytest.mark.contract
class TestPrivat24Contract:
    """Контрактні перевірки відповідей ендпоінтів Приват24."""

    def test_init_session_contract(self, monkeypatch):
        client = Privat24Client()

        # Мокуємо успішну відповідь від /api/p24/init
        mock_init_response = {
            "xref": "a" * 64,
            "base_url": "api/p24/pub/",
        }

        class MockResponse:
            status_code = 200

            def json(self):
                return mock_init_response

            def raise_for_status(self):
                pass

        monkeypatch.setattr(client.session, "post", lambda *args, **kwargs: MockResponse())

        xref, base_url = client.init_session()
        assert len(xref) == 64
        assert base_url == "api/p24/pub/"

    def test_bargaining_contract(self, monkeypatch):
        client = Privat24Client()
        client.xref = "a" * 64
        client.base_url = "api/p24/pub/"

        mock_bonds_response = [
            {
                "isin": "UA4000227185",
                "name": "Військові облігації",
                "currency": "UAH",
                "term": "2027-05-26",
                "priceBuy": 1056.23,
                "priceSell": 995.10,
                "rateBuy": 14.85,
                "rateSell": 17.50,
                "nominal": 1000.0,
                "issueDate": "2023-05-24",
                "active": True,
            }
        ]

        class MockResponse:
            status_code = 200

            def json(self):
                return mock_bonds_response

            def raise_for_status(self):
                pass

        monkeypatch.setattr(client.session, "post", lambda *args, **kwargs: MockResponse())

        raw_bonds = client.get_raw_bonds()
        assert isinstance(raw_bonds, list)
        assert len(raw_bonds) == 1
        item = raw_bonds[0]
        assert "isin" in item
        assert "currency" in item
        assert "priceBuy" in item
        assert "rateBuy" in item

    def test_limits_contract(self, monkeypatch):
        client = Privat24Client()
        client.xref = "a" * 64
        client.base_url = "api/p24/pub/"

        mock_limits_response = {
            "isin": "UA4000227185",
            "count": 85217,
            "minAmount": 1,
            "maxAmount": 85217,
            "active": True,
        }

        class MockResponse:
            status_code = 200

            def json(self):
                return mock_limits_response

            def raise_for_status(self):
                pass

        monkeypatch.setattr(client.session, "get", lambda *args, **kwargs: MockResponse())

        limits = client.get_limits("UA4000227185")
        assert limits["isin"] == "UA4000227185"
        assert limits["count"] == 85217
        assert limits["active"] is True

    def test_operations_contract(self, monkeypatch):
        client = Privat24Client()
        client.xref = "a" * 64
        client.base_url = "api/p24/pub/"

        mock_ops_response = {
            "isin": "UA4000227185",
            "operations": [
                {
                    "date": "2024-11-20",
                    "type": "KUPON",
                    "amount": 75.50,
                    "currency": "UAH",
                },
                {
                    "date": "2027-05-26",
                    "type": "PAYMENT",
                    "amount": 1000.0,
                    "currency": "UAH",
                },
            ],
        }

        class MockResponse:
            status_code = 200

            def json(self):
                return mock_ops_response

            def raise_for_status(self):
                pass

        monkeypatch.setattr(client.session, "post", lambda *args, **kwargs: MockResponse())

        ops = client.get_operations("UA4000227185")
        assert len(ops) == 2
        assert ops[0].event_type.value == "Купон"
        assert ops[1].event_type.value == "Погашення"

"""PBT tests for Notification Service."""
from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from hypothesis import given
from hypothesis import strategies as st

from core.models.tender import TenderModel, TenderStatus
from notifications.telegram import TelegramNotifier, _MAX_TG_LEN
from notifications.email_digest import EmailDigest, EmailDigestMessage


def _make_tender(tid: str, title: str) -> TenderModel:
    return TenderModel(
        id=f"bidzaar_{tid}", platform="bidzaar", external_id=tid,
        title=title, url=f"https://bidzaar.com/requests/public/{tid}",
        status=TenderStatus.QUALIFIED, qualification_tier="qualified",
    )


class TestTelegramNotifier:
    @given(count=st.integers(min_value=0, max_value=100_000))
    def test_message_within_telegram_limit(self, count: int):
        notifier = TelegramNotifier("token", ["123"], "https://example.com")
        text = notifier._format_message(count)
        assert len(text) <= _MAX_TG_LEN

    def test_empty_chat_ids_skips_silently(self):
        notifier = TelegramNotifier("token", [], "https://example.com")
        # Should not raise
        notifier.send_alert(5, {"bidzaar": 5})

    def test_message_contains_count(self):
        notifier = TelegramNotifier("token", ["123"], "https://example.com")
        text = notifier._format_message(42)
        assert "42" in text

    def test_message_contains_url_when_set(self):
        notifier = TelegramNotifier("token", ["123"], "https://myapp.com")
        text = notifier._format_message(1)
        assert "myapp.com" in text

    def test_message_no_url_when_empty(self):
        notifier = TelegramNotifier("token", ["123"], "")
        text = notifier._format_message(1)
        assert "http" not in text


class TestEmailDigest:
    def _make_digest(self, recipients=None):
        return EmailDigest(
            smtp_host="smtp.example.com", smtp_port=587,
            smtp_username="user", smtp_password="pass",
            smtp_from="from@example.com",
            recipients=recipients or ["a@b.com"],
        )

    @given(
        tenders=st.lists(
            st.builds(
                lambda tid, title: _make_tender(str(tid), title),
                tid=st.integers(min_value=1, max_value=99999),
                title=st.text(min_size=3, max_size=100),
            ),
            min_size=1, max_size=20,
        )
    )
    def test_all_urls_in_body(self, tenders):
        digest = self._make_digest()
        msg = digest.build_digest(tenders, "04.06.2026")
        for tender in tenders:
            assert tender.url in msg.body_text

    def test_empty_recipients_skips(self):
        digest = self._make_digest(recipients=[])
        msg = EmailDigestMessage(subject="S", body_text="B", recipients=[])
        digest.send(msg)  # should not raise

    def test_subject_contains_date(self):
        digest = self._make_digest()
        msg = digest.build_digest([], "04.06.2026")
        assert "04.06.2026" in msg.subject

    def test_empty_tenders_handled(self):
        digest = self._make_digest()
        msg = digest.build_digest([], "04.06.2026")
        assert "0 шт." in msg.subject
        assert msg.body_text  # not empty

    @given(emails=st.lists(
        st.emails(), min_size=1, max_size=10
    ))
    def test_recipients_parsed_no_empty(self, emails):
        raw = ",".join(emails) + ","  # trailing comma
        recipients = [e.strip() for e in raw.split(",") if e.strip()]
        assert all(r for r in recipients)

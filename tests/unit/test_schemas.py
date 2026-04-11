"""
Unit tests for Pydantic schemas — validation and serialization.
"""

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.auth import (
    RegistrationRequest,
    Token,
    TokenData,
    UserContext,
    UserResponse,
)
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    Citation,
    MessageOut,
    ChatHistoryResponse,
)
from app.schemas.feedback import FeedbackCreate, FeedbackResponse
from app.schemas.knowledgebase import KBCreate, KBResponse
from app.schemas.document import UploadResponse, DocumentStatusResponse


class TestRegistrationRequest:
    def test_valid_request(self):
        req = RegistrationRequest(
            org_name="Test Org", email="user@example.com", password="secret123"
        )
        assert req.org_name == "Test Org"
        assert req.email == "user@example.com"

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            RegistrationRequest(
                org_name="Test Org", email="not-an-email", password="secret123"
            )

    def test_missing_fields(self):
        with pytest.raises(ValidationError):
            RegistrationRequest()

    def test_empty_org_name_allowed(self):
        req = RegistrationRequest(org_name="", email="a@b.com", password="secret123")
        assert req.org_name == ""


class TestToken:
    def test_valid_token(self):
        t = Token(access_token="abc", token_type="bearer")
        assert t.access_token == "abc"
        assert t.token_type == "bearer"


class TestTokenData:
    def test_defaults_none(self):
        td = TokenData()
        assert td.user_id is None
        assert td.org_id is None

    def test_with_values(self):
        uid = uuid.uuid4()
        oid = uuid.uuid4()
        td = TokenData(user_id=uid, org_id=oid)
        assert td.user_id == uid
        assert td.org_id == oid


class TestUserContext:
    def test_valid_context(self):
        uid = uuid.uuid4()
        oid = uuid.uuid4()
        ctx = UserContext(user_id=uid, org_id=oid, email="a@b.com")
        assert ctx.role == "user"

    def test_admin_role(self):
        ctx = UserContext(
            user_id=uuid.uuid4(), org_id=uuid.uuid4(), email="a@b.com", role="admin"
        )
        assert ctx.role == "admin"

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            UserContext(user_id=uuid.uuid4(), org_id=uuid.uuid4(), email="bad-email")


class TestUserResponse:
    def test_from_attributes(self):
        uid = uuid.uuid4()
        oid = uuid.uuid4()

        class FakeUser:
            id = uid
            email = "user@example.com"
            org_id = oid
            role = "admin"

        resp = UserResponse.model_validate(FakeUser())
        assert resp.id == uid
        assert resp.email == "user@example.com"
        assert resp.org_id == oid
        assert resp.role == "admin"


class TestChatRequest:
    def test_valid_request(self):
        kb_id = uuid.uuid4()
        req = ChatRequest(kb_id=kb_id, message="What is RAG?")
        assert req.top_k == 6
        assert req.chat_id is None

    def test_custom_top_k(self):
        kb_id = uuid.uuid4()
        req = ChatRequest(kb_id=kb_id, message="Hello", top_k=10)
        assert req.top_k == 10

    def test_top_k_minimum(self):
        kb_id = uuid.uuid4()
        with pytest.raises(ValidationError):
            ChatRequest(kb_id=kb_id, message="Hi", top_k=0)

    def test_top_k_maximum(self):
        kb_id = uuid.uuid4()
        with pytest.raises(ValidationError):
            ChatRequest(kb_id=kb_id, message="Hi", top_k=21)

    def test_empty_message_rejected(self):
        kb_id = uuid.uuid4()
        with pytest.raises(ValidationError):
            ChatRequest(kb_id=kb_id, message="")

    def test_with_chat_id(self):
        kb_id = uuid.uuid4()
        chat_id = uuid.uuid4()
        req = ChatRequest(kb_id=kb_id, message="Follow-up", chat_id=chat_id)
        assert req.chat_id == chat_id


class TestCitation:
    def test_valid_citation(self):
        c = Citation(chunk_id="c1", document_id="d1", score=0.95)
        assert c.score == 0.95


class TestChatResponse:
    def test_valid_response(self):
        r = ChatResponse(
            chat_id=uuid.uuid4(),
            message_id=uuid.uuid4(),
            answer="RAG is...",
            citations=[Citation(chunk_id="c1", document_id="d1", score=0.9)],
        )
        assert len(r.citations) == 1


class TestFeedbackCreate:
    def test_thumbs_up(self):
        f = FeedbackCreate(message_id=uuid.uuid4(), rating=1)
        assert f.rating == 1

    def test_thumbs_down(self):
        f = FeedbackCreate(message_id=uuid.uuid4(), rating=-1)
        assert f.rating == -1

    def test_neutral_rating(self):
        f = FeedbackCreate(message_id=uuid.uuid4(), rating=0)
        assert f.rating == 0

    def test_rating_above_1_rejected(self):
        with pytest.raises(ValidationError):
            FeedbackCreate(message_id=uuid.uuid4(), rating=2)

    def test_rating_below_minus_1_rejected(self):
        with pytest.raises(ValidationError):
            FeedbackCreate(message_id=uuid.uuid4(), rating=-2)

    def test_with_note(self):
        f = FeedbackCreate(message_id=uuid.uuid4(), rating=1, note="Great answer!")
        assert f.note == "Great answer!"

    def test_note_max_length(self):
        with pytest.raises(ValidationError):
            FeedbackCreate(message_id=uuid.uuid4(), rating=1, note="x" * 2001)


class TestFeedbackResponse:
    def test_from_attributes(self):
        fid = uuid.uuid4()
        mid = uuid.uuid4()

        class FakeFeedback:
            id = fid
            message_id = mid
            rating = 1
            note = "Good"

        resp = FeedbackResponse.model_validate(FakeFeedback())
        assert resp.id == fid
        assert resp.rating == 1
        assert resp.note == "Good"


class TestKBCreate:
    def test_valid_name(self):
        kb = KBCreate(name="My KB")
        assert kb.name == "My KB"

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            KBCreate(name="")

    def test_name_too_long(self):
        with pytest.raises(ValidationError):
            KBCreate(name="x" * 256)


class TestKBResponse:
    def test_from_attributes(self):
        kid = uuid.uuid4()
        oid = uuid.uuid4()

        class FakeKB:
            id = kid
            org_id = oid
            name = "Test KB"
            created_at = "2025-01-01T00:00:00Z"

        resp = KBResponse.model_validate(FakeKB())
        assert resp.id == kid
        assert resp.name == "Test KB"


class TestUploadResponse:
    def test_valid(self):
        r = UploadResponse(
            document_id="123", filename="test.pdf", status="PENDING", message="OK"
        )
        assert r.status == "PENDING"


class TestDocumentStatusResponse:
    def test_validation_alias_id(self):
        did = uuid.uuid4()
        kid = uuid.uuid4()
        now = "2025-01-01T00:00:00Z"

        class FakeDoc:
            id = did
            kb_id = kid
            filename = "test.pdf"
            status = "completed"
            error_msg = None
            created_at = now
            updated_at = now

        resp = DocumentStatusResponse.model_validate(FakeDoc())
        assert resp.document_id == did
        assert resp.status == "completed"

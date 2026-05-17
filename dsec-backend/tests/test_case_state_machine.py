"""Tests for case state machine transitions."""
import pytest
from app.models.case import Case, CaseStatusEnum
from app.models.user import User, RoleEnum
from app.services.case.case_service import apply_transition
from app.core.exceptions import InvalidTransitionError, ForbiddenError
import uuid


def make_user(role: RoleEnum) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="hashed-password",
        role=role,
        org_id=uuid.uuid4(),
        is_active=True,
    )


def make_case(status: CaseStatusEnum) -> Case:
    return Case(
        id=uuid.uuid4(),
        title="Test Case",
        status=status,
        org_id=uuid.uuid4(),
        created_by=uuid.uuid4(),
    )


class TestStateMachine:
    def test_draft_to_submitted(self):
        case = make_case(CaseStatusEnum.DRAFT)
        agent = make_user(RoleEnum.AGENT)
        new_status = apply_transition(case, "submit", agent)
        assert new_status == CaseStatusEnum.SUBMITTED

    def test_invalid_transition(self):
        case = make_case(CaseStatusEnum.DRAFT)
        agent = make_user(RoleEnum.AGENT)
        with pytest.raises(InvalidTransitionError):
            apply_transition(case, "approve", agent)

    def test_wrong_role_cannot_submit(self):
        case = make_case(CaseStatusEnum.AI_REVIEWED)
        agent = make_user(RoleEnum.AGENT)
        with pytest.raises(ForbiddenError):
            apply_transition(case, "platform_complete", agent)

    def test_dji_can_approve(self):
        case = make_case(CaseStatusEnum.DJI_REVIEWED)
        dji_se = make_user(RoleEnum.DJI_SE)
        new_status = apply_transition(case, "approve", dji_se)
        assert new_status == CaseStatusEnum.APPROVED

    def test_dji_can_reject(self):
        case = make_case(CaseStatusEnum.DJI_REVIEWED)
        dji_se = make_user(RoleEnum.DJI_SE)
        new_status = apply_transition(case, "reject", dji_se)
        assert new_status == CaseStatusEnum.REJECTED

    def test_system_transition_no_actor(self):
        case = make_case(CaseStatusEnum.SUBMITTED)
        new_status = apply_transition(case, "ai_complete")
        assert new_status == CaseStatusEnum.AI_REVIEWED

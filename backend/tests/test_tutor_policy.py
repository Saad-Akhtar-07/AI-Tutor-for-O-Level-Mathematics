import pytest
from pydantic import ValidationError

from backend.app.schemas.tutor import EvaluationResult, SocraticReply
from backend.app.services.tutor import choose_policy


def evaluation(assessment: str, readability: str = "clear") -> EvaluationResult:
    return EvaluationResult(
        assessment=assessment,
        marks_awarded=1 if assessment == "correct" else 0,
        readability=readability,
        observed_work="3/5",
        criteria=[],
        primary_error=None,
        positive_observation="The favourable count is correct.",
        guiding_question="How many outcomes are there altogether?",
        next_step_hint="Use the total number of outcomes as the denominator.",
        confidence=0.9,
    )


def test_policy_progresses_hints_without_revealing_a_solution() -> None:
    first = choose_policy(evaluation("incorrect"), 0)
    second = choose_policy(evaluation("incorrect"), 1)
    third = choose_policy(evaluation("incorrect"), 2)

    assert (first.action, first.hint_level) == ("guiding_question", 1)
    assert (second.action, second.hint_level) == ("targeted_hint", 2)
    assert (third.action, third.hint_level) == ("worked_next_step", 3)
    assert "3/8" not in first.feedback


def test_policy_handles_correct_and_unreadable_work() -> None:
    assert choose_policy(evaluation("correct"), 0).action == "move_forward"
    unclear = choose_policy(evaluation("unassessable", "unreadable"), 0)
    assert unclear.action == "request_clearer_response"
    assert unclear.hint_level == 0


def test_socratic_reply_schema_rejects_answer_reveals() -> None:
    with pytest.raises(ValidationError):
        SocraticReply(
            message="Here is the final answer.",
            teaching_move="small_hint",
            should_revise_work=False,
            reveals_final_answer=True,
        )

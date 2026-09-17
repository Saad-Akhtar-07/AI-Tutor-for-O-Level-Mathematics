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
    assert (third.action, third.hint_level) == ("targeted_hint", 3)
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


def test_chat_context_is_bounded_without_mutating_saved_history(monkeypatch):
    import copy
    import json
    from backend.app.config import get_settings
    from backend.app.services.openrouter import ModelCompletion
    from backend.app.services.tutor import run_tutor_chat
    captured = {}
    class Client:
        def __init__(self, *args, **kwargs):
            pass
        def structured_completion(self, **kwargs):
            captured.update(kwargs)
            return ModelCompletion(json.dumps(dict(message="How many outcomes?", teaching_move="ask_question",
                should_revise_work=False, reveals_final_answer=False)), "test", {})
    monkeypatch.setattr("backend.app.services.tutor.OpenRouterClient", Client)
    snapshot = {"learner_work": {"typed_work": "3/5"}, "conversation": [
        {"learner": str(i) + "a" * 1000, "tutor": "b" * 1000} for i in range(12)]}
    original = copy.deepcopy(snapshot)
    run_tutor_chat(get_settings(), snapshot, "Help")
    sent = json.loads(captured["messages"][1]["content"])
    assert snapshot == original
    assert 0 < len(sent["conversation"]) < 12
    assert sent["conversation"][-1] == snapshot["conversation"][-1]
    assert sent["learner_work"] == snapshot["learner_work"]


@pytest.mark.parametrize("move,level", [
    ("formula_reminder", 2), ("explain_concept", 2), ("small_hint", 1),
    ("worked_step", 3), ("similar_example", 3), ("ask_question", 1),
])
def test_assessment_uses_selected_support_instead_of_attempt_count(move, level):
    result = evaluation("incorrect").model_copy(update={"teaching_feedback": SocraticReply(
        message="Use favourable outcomes divided by all equally likely outcomes.",
        teaching_move=move, support_level=level, target_concept="probability",
        should_revise_work=True, reveals_final_answer=False,
    )})
    for attempts in (0, 1, 5):
        decision = choose_policy(result, attempts)
        assert decision.action == move
        assert decision.hint_level == level
        assert decision.feedback == result.teaching_feedback.message


@pytest.mark.parametrize("error", ["calculation_error", "notation_error", "misread_question"])
def test_legacy_feedback_does_not_quiz_students_for_a_specific_slip(error):
    from backend.app.schemas.tutor import PrimaryError
    result = evaluation("incorrect").model_copy(update={"primary_error": PrimaryError(
        type=error, target_concept="probability", description="Check the denominator.",
    )})
    assert choose_policy(result, 0).action == "targeted_hint"


def test_support_context_does_not_confuse_old_work_with_current_work():
    from backend.app.services.tutor import teaching_context
    snapshot = {
        "learner_work": {"revision": 3},
        "conversation": [
            {"teaching_move": "ask_question", "response_revision": 2},
            {"teaching_move": "ask_question", "response_revision": 3},
            {"teaching_move": "check_understanding", "response_revision": 3},
        ],
        "latest_review": {"reviewed_response_revision": 2},
    }
    context = teaching_context(snapshot)
    assert context["consecutive_questions_on_current_work"] == 2
    assert context["assessment_matches_current_work"] is False
    snapshot["learner_work"]["revision"] = 4
    assert teaching_context(snapshot)["consecutive_questions_on_current_work"] == 0
    snapshot["learner_work"]["revision"] = None
    snapshot["latest_review"]["reviewed_response_revision"] = None
    assert teaching_context(snapshot)["assessment_matches_current_work"] is False


def test_chat_selects_and_remembers_support_with_one_provider_call(monkeypatch):
    import json
    from backend.app.config import get_settings
    from backend.app.services.openrouter import ModelCompletion
    from backend.app.services.tutor import run_tutor_chat
    calls = []
    class Client:
        def __init__(self, *args, **kwargs):
            pass
        def structured_completion(self, **kwargs):
            calls.append(kwargs)
            return ModelCompletion(json.dumps(dict(
                message="P(event) = favourable outcomes / total equally likely outcomes.",
                teaching_move="formula_reminder", support_level=2, target_concept="probability",
                should_revise_work=False, reveals_final_answer=False,
            )), "test", {"total_tokens": 50})
    monkeypatch.setattr("backend.app.services.tutor.OpenRouterClient", Client)
    result = run_tutor_chat(get_settings(), {"learner_work": {"revision": 1}}, "I forgot the formula")
    assert len(calls) == 1
    assert result.reply.teaching_move == "formula_reminder"
    assert result.usage["teaching"] == {"support_level": 2, "target_concept": "probability"}
    assert result.usage["total_tokens"] == 50
    assert calls[0]["max_tokens"] <= 1000


def test_assessment_selects_feedback_in_the_existing_marking_call(monkeypatch):
    import json
    from backend.app.config import get_settings
    from backend.app.services.openrouter import ModelCompletion
    from backend.app.services.tutor import evaluate_snapshot
    calls = []
    class Client:
        def structured_completion(self, **kwargs):
            calls.append(kwargs)
            result = evaluation("incorrect").model_copy(update={"teaching_feedback": SocraticReply(
                message="The denominator counts all outcomes, including unfavourable ones.",
                teaching_move="explain_concept", support_level=2, target_concept="sample space",
                should_revise_work=True, reveals_final_answer=False,
            )})
            completion = ModelCompletion(result.model_dump_json(), "test", {})
            kwargs["validate"](completion)
            return completion
    snapshot = {
        "question": {}, "target_part": {"marks": 1},
        "mark_scheme": {"answer": "3/8", "marking_points": []},
        "learner_work": {"typed_work": "3/5"},
        "previous_review": {"feedback_already_shown": "Count all outcomes."},
        "conversation": [{"learner": "Still confused", "tutor": "Count all outcomes."}],
    }
    result, _ = evaluate_snapshot(Client(), get_settings(), snapshot, None)
    assert len(calls) == 1
    sent = json.loads(calls[0]["messages"][1]["content"])
    assert sent["previous_support"] == snapshot["conversation"]
    assert sent["previous_review"] == snapshot["previous_review"]
    assert choose_policy(result, 0).action == "explain_concept"


def test_teaching_schema_requires_compatibility_fields_for_strict_providers():
    from backend.app.services.tutor import teaching_schema
    def check(node):
        if isinstance(node, dict):
            assert "default" not in node
            if "properties" in node:
                assert set(node["required"]) == set(node["properties"])
                assert node["additionalProperties"] is False
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for value in node:
                check(value)
    check(teaching_schema(SocraticReply))
    check(teaching_schema(EvaluationResult))


@pytest.mark.parametrize("answer,message", [
    ("0.375", "The correct decimal is 0.375."),
    ("0.375", "The probability is .375."),
    ("$\\frac{3}{8}$", "That gives a probability of 37.5%."),
    ("$\\frac{3}{8}$", "The final answer is 3/8."),
    ("0", "The probability is 0."),
])
def test_numeric_answer_leaks_become_useful_guidance(answer, message):
    from backend.app.services.tutor import protect_final_answer
    reply = SocraticReply(message=message, teaching_move="worked_step", support_level=3,
        target_concept="probability", should_revise_work=True, reveals_final_answer=False)
    result = protect_final_answer(reply, {"private_mark_scheme": {"answer": answer}})
    assert result.teaching_move == "small_hint"
    assert "multiply your decimal by the denominator" in result.message


def test_answer_backstop_preserves_formulas_examples_and_matching_correct_work():
    from backend.app.services.tutor import protect_final_answer
    context = {"private_mark_scheme": {"answer": "0.375"}, "learner_work": {"revision": 2}}
    for message in ["P(event) = favourable / total.", "With 2 red and 3 blue counters, P(red) = 2/5 = 0.4."]:
        reply = SocraticReply(message=message, teaching_move="similar_example", support_level=3,
            target_concept="probability", should_revise_work=False, reveals_final_answer=False)
        assert protect_final_answer(reply, context) == reply
    confirmation = reply.model_copy(update={"message": "Your assessed probability of 0.375 is correct."})
    context["latest_review"] = {"reviewed_response_revision": 2, "evaluation": {"assessment": "correct"}}
    assert protect_final_answer(confirmation, context) == confirmation
    context["learner_work"]["revision"] = 3
    assert protect_final_answer(confirmation, context).teaching_move == "small_hint"


def test_numeric_answer_safeguard_does_not_retry_the_provider(monkeypatch):
    import json
    from backend.app.config import get_settings
    from backend.app.services.openrouter import ModelCompletion
    from backend.app.services.tutor import run_tutor_chat
    calls = []
    class Client:
        def __init__(self, *args, **kwargs):
            pass
        def structured_completion(self, **kwargs):
            calls.append(kwargs)
            return ModelCompletion(json.dumps(dict(
                message="The correct decimal is 0.375.", teaching_move="worked_step",
                support_level=3, target_concept="decimal division",
                should_revise_work=True, reveals_final_answer=False,
            )), "test", {})
    monkeypatch.setattr("backend.app.services.tutor.OpenRouterClient", Client)
    result = run_tutor_chat(get_settings(), {
        "private_mark_scheme": {"answer": "0.375"}, "learner_work": {"typed_work": "3/8 = 0.325"},
    }, "Check my calculation")
    assert len(calls) == 1
    assert "0.375" not in result.reply.message
    assert result.reply.teaching_move == "small_hint"
    assert result.usage["teaching"]["support_level"] == 1

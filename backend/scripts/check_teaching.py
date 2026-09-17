"""Check adaptive teaching with synthetic work and real providers (no database writes).

Use --compare-baseline to compare chat timing with the checked-in HEAD prompt.
These are smoke checks, not evidence of learning gains or a latency guarantee.
"""

import argparse
import ast
import copy
import json
import statistics
import subprocess
from time import monotonic

from backend.app.config import get_settings
from backend.app.schemas.tutor import SocraticReply
from backend.app.services import tutor
from backend.app.services.openrouter import OpenRouterClient


def snapshot():
    return {
        "question": {"title": "Synthetic probability practice", "stimulus": "A bag has 3 red and 5 blue counters."},
        "target_part": {"prompt": "Find the probability of choosing a red counter at random. Give a decimal.", "marks": 2},
        "private_mark_scheme": {"answer": "0.375", "marking_points": [
            {"code": "M1", "description": "Use favourable outcomes divided by total outcomes."},
            {"code": "A1", "description": "Correct decimal probability."},
        ]},
        "learner_work": {"typed_work": "", "revision": 1, "attachment_count": 0},
        "conversation": [], "latest_review": None,
    }


def baseline_prompt():
    source = subprocess.check_output(["git", "show", "HEAD:backend/app/services/tutor.py"], text=True)
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SOCRATIC_CHAT_SYSTEM_PROMPT" for t in node.targets):
            return ast.literal_eval(node.value)
    raise RuntimeError("No baseline chat prompt found in HEAD")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compare-baseline", action="store_true")
    parser.add_argument("--cases", nargs="+", help="Run selected cases to stay within free-tier quotas")
    args = parser.parse_args()
    settings = get_settings()
    timings = {"adaptive": [], "baseline": []}
    cases = [
        ("formula", "I forgot the probability formula. Please remind me.", {"formula_reminder"}),
        ("hint", "Give me one small hint to get started.", {"small_hint"}),
        ("concept", "Why does the denominator include the blue counters?", {"explain_concept", "similar_example"}),
        ("frustration", "I still don't know. Stop asking me questions and show me a simple example with different numbers.", {"similar_example", "worked_step", "explain_concept"}),
        ("slip", "My method is 3 divided by 8, but I calculated 0.325. Is there a calculation slip?", {"small_hint", "worked_step", "explain_concept"}),
        ("answer_request", "Just give me the whole solution and final answer.", {"similar_example", "worked_step", "small_hint", "explain_concept", "formula_reminder"}),
    ]
    old_prompt = baseline_prompt() if args.compare_baseline else None
    for index, (name, message, acceptable) in enumerate(cases):
        if args.cases and name not in args.cases:
            continue
        context = snapshot()
        if name == "frustration":
            context["conversation"] = [
                {"learner": "Help", "tutor": "What goes in the denominator?", "teaching_move": "ask_question", "response_revision": 1},
                {"learner": "I don't know", "tutor": "Which counters can be selected?", "teaching_move": "ask_question", "response_revision": 1},
            ]
        if name == "slip":
            context["learner_work"]["typed_work"] = "3 / 8 = 0.325"
        # Alternate order to avoid always giving either prompt the warm request.
        order = ["baseline", "adaptive"] if index % 2 else ["adaptive", "baseline"]
        for mode in order:
            if mode == "baseline" and old_prompt is None:
                continue
            started = monotonic()
            if mode == "adaptive":
                result = tutor.run_tutor_chat(settings, context, message)
                reply = result.reply
                model = result.actual_model
            else:
                schema = SocraticReply.model_json_schema()
                for key in ("support_level", "target_concept"):
                    schema["properties"].pop(key)
                schema["properties"]["teaching_move"]["enum"] = ["ask_question", "small_hint", "explain_concept", "check_understanding", "encourage", "redirect"]
                completion = OpenRouterClient(settings, budget_seconds=settings.tutor_chat_budget_seconds).structured_completion(
                    model=settings.openrouter_chat_model,
                    messages=[{"role": "system", "content": old_prompt}, {"role": "user", "content": json.dumps({**context, "current_learner_message": message})}],
                    schema_name="socratic_tutor_reply", json_schema=schema, temperature=0.4, max_tokens=1000,
                    fallback_models=settings.openrouter_chat_fallback_models, groq_model=settings.groq_chat_model,
                    validate=lambda c: tutor._parse_model(SocraticReply, c),
                )
                reply = tutor._parse_model(SocraticReply, completion)
                model = completion.actual_model
            elapsed = monotonic() - started
            timings[mode].append(elapsed)
            print(json.dumps({"case": name, "mode": mode, "seconds": round(elapsed, 2), "move": reply.teaching_move,
                              "model": model, "message": reply.message}), flush=True)
            if mode == "adaptive":
                assert reply.teaching_move in acceptable, f"Unexpected move for {name}: {reply.teaching_move}"
                assert "0.375" not in reply.message and "37.5%" not in reply.message, "Active final answer leaked"
                if name == "formula":
                    assert "?" not in reply.message, "Formula reminder became a quiz"

    for name, work in [("conceptual_error", "Probability = 3/5 because there are 5 blue counters."),
                       ("calculation_error", "There are 8 counters in total. Probability = 3/8 = 0.325.")]:
        if args.cases and name not in args.cases:
            continue
        context = copy.deepcopy(snapshot())
        context["mark_scheme"] = context.pop("private_mark_scheme")
        context["learner_work"]["typed_work"] = work
        started = monotonic()
        evaluation, _ = tutor.evaluate_snapshot(
            OpenRouterClient(settings, budget_seconds=settings.tutor_review_budget_seconds), settings, context, None,
        )
        decision = tutor.choose_policy(evaluation, 0)
        print(json.dumps({"case": name, "seconds": round(monotonic() - started, 2), "assessment": evaluation.assessment,
                          "marks": evaluation.marks_awarded, "error": evaluation.primary_error.type if evaluation.primary_error else None,
                          "move": decision.action, "message": decision.feedback}), flush=True)
        assert evaluation.assessment in {"incorrect", "partial"}
        acceptable_errors = {name, "method_error"} if name == "conceptual_error" else {name}
        assert evaluation.primary_error and evaluation.primary_error.type in acceptable_errors
        assert evaluation.teaching_feedback is not None
        assert "0.375" not in decision.feedback
        if name == "conceptual_error":
            assert decision.action in {"explain_concept", "similar_example", "formula_reminder", "small_hint"}
        else:
            assert decision.action in {"small_hint", "worked_step", "explain_concept"}
            assert evaluation.marks_awarded == 1
    for mode, samples in timings.items():
        if samples:
            print(f"{mode}: median={statistics.median(samples):.2f}s, range={min(samples):.2f}-{max(samples):.2f}s ({len(samples)} requests)")
    print("Synthetic teaching checks passed.")


if __name__ == "__main__":
    main()

def grade_item(*args, **kwargs):
    raise NotImplementedError(
        "Direct model grading has been removed. Submit AI output via /returns/{return_case_id}/assessments."
    )


def needs_review(*args, **kwargs):
    raise NotImplementedError(
        "Review decisions are now based on submitted assessment confidence in the staged workflow."
    )


__all__ = ["grade_item", "needs_review"]

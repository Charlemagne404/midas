import pytest

from scripts.audit_proposal_outcomes import summarize


def row(identity, completion, left, right, partition="train"):
    return {
        "base_episode_id": identity,
        "partition": partition,
        "initial_outcome": {
            "completion": completion,
            "unmatched": int(left != right),
            "residual_unmatched_shares": str(abs(left - right)),
            "filled_shares_by_asset": {"yes": str(left), "no": str(right)},
        },
    }


def test_incomplete_does_not_imply_unmatched_and_groups_have_equal_weight():
    rows = [row("a", 0, 0, 0), row("a", 0, 2, 2), row("a", 1, 3, 3), row("b", 0, 4, 0)]
    report = summarize(rows)
    assert report["paired_outcome_counts"]["incomplete_matched"] == 2
    assert report["unmatched_frequency_given_incomplete"] == 1 / 3
    assert report["group_mean_residual_shares"] == 2
    assert report == summarize(rows)


@pytest.mark.parametrize("mutation", ["test", "nan", "wrong_residual", "wrong_label", "missing"])
def test_rejects_held_out_or_inconsistent_evidence(mutation):
    value = row("a", 0, 2, 0)
    if mutation == "test":
        value["partition"] = "test"
    elif mutation == "nan":
        value["initial_outcome"]["filled_shares_by_asset"]["yes"] = "NaN"
    elif mutation == "wrong_residual":
        value["initial_outcome"]["residual_unmatched_shares"] = "1"
    elif mutation == "wrong_label":
        value["initial_outcome"]["unmatched"] = 0
    else:
        del value["initial_outcome"]
    with pytest.raises(ValueError):
        summarize([value])

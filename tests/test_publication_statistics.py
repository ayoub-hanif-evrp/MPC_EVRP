from scripts.audit_frozen_studies import cluster_sign_flip, holm_adjust


def test_exact_parent_sign_flip_counts_all_sign_patterns():
    assert cluster_sign_flip([1] * 6) == 2 / 64
    assert cluster_sign_flip([0] * 6) == 1
    assert cluster_sign_flip([1, -1]) == 1


def test_holm_adjustment_is_stepdown_and_bounded():
    assert holm_adjust({"a": .01, "b": .04, "c": .03}) == {
        "a": .03, "c": .06, "b": .06}
    assert holm_adjust({"a": .8, "b": .9}) == {"a": 1, "b": 1}

import pytest

from linx_shared.messaging.policy import (
    FailurePolicy,
    InvalidMessageError,
    ProcessOutcome,
)


def test_poison_message_goes_straight_to_dead_letter():
    policy = FailurePolicy()

    outcome = policy.decide(InvalidMessageError("bad"), attempt=1)

    assert outcome is ProcessOutcome.DEAD_LETTER


def test_transient_failure_retries_until_max_attempts():
    policy = FailurePolicy(max_attempts=3, delays=(1.0, 2.0))

    assert policy.decide(RuntimeError("db"), attempt=1) is ProcessOutcome.RETRY
    assert policy.decide(RuntimeError("db"), attempt=2) is ProcessOutcome.RETRY
    assert (
        policy.decide(RuntimeError("db"), attempt=3)
        is ProcessOutcome.DEAD_LETTER
    )


def test_delay_sequence_is_capped_at_last_value():
    policy = FailurePolicy(delays=(1.0, 2.0))

    assert policy.delay(1) == 1.0
    assert policy.delay(2) == 2.0
    assert policy.delay(10) == 2.0


def test_policy_rejects_invalid_max_attempts():
    with pytest.raises(ValueError, match="max_attempts"):
        FailurePolicy(max_attempts=0)


def test_policy_rejects_negative_delay():
    with pytest.raises(ValueError, match="negativo"):
        FailurePolicy(delays=(-1.0,))

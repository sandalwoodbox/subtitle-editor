import pytest

from .factories import SubtitleFactory


@pytest.fixture(autouse=True)
def reset_factory_boy_sequences():
    SubtitleFactory.reset_sequence()

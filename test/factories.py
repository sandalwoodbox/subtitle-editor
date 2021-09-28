from datetime import timedelta

import factory
import srt


class SubtitleFactory(factory.Factory):
    class Meta:
        model = srt.Subtitle

    index = factory.Sequence(lambda n: n)
    start = factory.Sequence(lambda n: n * timedelta(seconds=1))
    end = factory.Sequence(lambda n: n * timedelta(seconds=1))
    content = factory.Faker("sentence")

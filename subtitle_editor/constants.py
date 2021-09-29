from datetime import timedelta

FRAMERATE = 25
ONE_FRAME = timedelta(milliseconds=1000 / FRAMERATE)
ONE_SECOND = timedelta(seconds=1)
UNSET_TIME = timedelta(-1)

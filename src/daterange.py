"""'수집 대상일'과 그 하루의 시간창을 계산 (pipeline·collector 공용).

운영 시나리오: 매일 23:59(KST)에 실행해 '그날 하루' 발행분을 수집한다.
다음 날 아침에 일어나면 '어제 하루'에 무슨 일이 있었는지 한 번에 볼 수 있다.

GitHub Actions 예약 작업이 자정을 넘겨 지연 실행될 수 있으므로,
실행 시각이 새벽(04시 이전)이면 '그 전날'을 대상일로 보정한다.
(예: 23:59 작업이 00:10에 실행돼도 의도한 '어제' 데이터를 수집)
"""

from datetime import datetime, timedelta

# 이 시각(로컬) 이전에 실행되면 전날을 대상일로 본다.
EARLY_HOUR_ROLLBACK = 4


def target_date(now=None):
    now = now or datetime.now().astimezone()
    if now.hour < EARLY_HOUR_ROLLBACK:
        return (now - timedelta(days=1)).date()
    return now.date()


def day_window(now=None):
    """대상일의 [00:00, 다음날 00:00) 시간창을 (start, end) aware datetime으로 반환."""
    now = now or datetime.now().astimezone()
    d = target_date(now)
    start = datetime(d.year, d.month, d.day, tzinfo=now.tzinfo)
    return start, start + timedelta(days=1)

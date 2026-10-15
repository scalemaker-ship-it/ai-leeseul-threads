"""scheduled/ 폴더의 날짜 예약 원고를 그날(KST) 1건 발행한다.

파일 첫 줄 "# DATE: YYYY-MM-DD" 가 오늘이면 발행. 크론이 밀려 자정을 넘긴 경우를 위해
새벽 6시 전까지는 어제 날짜 원고도 발행한다. posted_log.json 의 id(sched:파일명)로 중복 차단.
사용: python post_scheduled.py [--dry-run] [--date YYYY-MM-DD]
"""
import argparse
import glob
import os
import sys
from datetime import datetime, timedelta

from threads_post import (KST, _load_json, LOG_FILE, append_posted_log, post_to_threads,
                          require_env, strip_emoji, wrap_for_threads)

_HERE = os.path.dirname(os.path.abspath(__file__))


def read_post(path: str):
    with open(path, encoding="utf-8") as f:
        first, _, body = f.read().partition("\n")
    if not first.startswith("# DATE:"):
        return None, None
    return first.split(":", 1)[1].strip(), wrap_for_threads(strip_emoji(body.strip()))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--date", help="이 날짜 원고를 대상으로 확인(dry-run 검증용)")
    a = ap.parse_args()

    now = datetime.now(KST)
    targets = {a.date} if a.date else {now.strftime("%Y-%m-%d")}
    if not a.date and now.hour < 6:
        targets.add((now - timedelta(days=1)).strftime("%Y-%m-%d"))

    posted = {e["id"] for e in _load_json(LOG_FILE, [])}
    for path in sorted(glob.glob(os.path.join(_HERE, "scheduled", "*.txt"))):
        date, text = read_post(path)
        pid = "sched:" + os.path.basename(path)
        if date not in targets:
            continue
        if pid in posted:
            print(f"[스킵] 이미 발행: {pid}")
            continue
        print(f"=== {pid} (예약일 {date}) ===\n{text}\n=== 글자 수: {len(text)}자 ===")
        if len(text) > 500:
            sys.exit(f"[오류] 500자 초과({len(text)}자)")
        if a.dry_run:
            print("(dry-run) 게시하지 않습니다.")
            continue
        post_id = post_to_threads(require_env("THREADS_USER_ID"), require_env("THREADS_ACCESS_TOKEN"), text)
        append_posted_log({"date": now.strftime("%Y-%m-%d"), "id": pid, "post_id": post_id})
        print(f"게시 완료: {post_id}")
        return  # 하루 1건
    print(f"오늘({', '.join(sorted(targets))}) 발행할 예약 원고 없음.")


if __name__ == "__main__":
    main()

"""영상 1개 + 글을 @ai_leeseul 스레드에 게시한다 (원샷, workflow_dispatch 전용).

영상은 공개 URL 이어야 한다(Threads 가 직접 내려받음). 컨테이너 생성 → 처리 완료 대기 → 발행.
사용: python post_video.py --video-url URL --text-file video_posts/xxx.txt [--dry-run]
"""
import argparse
import os
import sys
import time

import requests

API = "https://graph.threads.net/v1.0"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video-url", required=True)
    ap.add_argument("--text-file", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    text = open(a.text_file, encoding="utf-8").read().strip()
    print(f"글 {len(text)}자 / 영상 {a.video_url}")
    if len(text) > 500:
        sys.exit("글이 500자를 넘습니다(Threads 제한).")
    if a.dry_run:
        print(text)
        return

    uid = os.environ["THREADS_USER_ID"]
    tok = os.environ["THREADS_ACCESS_TOKEN"]
    r = requests.post(f"{API}/{uid}/threads", data={"media_type": "VIDEO", "video_url": a.video_url, "text": text, "access_token": tok}, timeout=60)
    r.raise_for_status()
    cid = r.json()["id"]
    print("컨테이너:", cid)

    for _ in range(60):  # 최대 10분
        s = requests.get(f"{API}/{cid}", params={"fields": "status,error_message", "access_token": tok}, timeout=30).json()
        print("상태:", s)
        if s.get("status") == "FINISHED":
            break
        if s.get("status") in ("ERROR", "EXPIRED"):
            sys.exit(f"영상 처리 실패: {s}")
        time.sleep(10)
    else:
        sys.exit("영상 처리 시간 초과")

    p = requests.post(f"{API}/{uid}/threads_publish", data={"creation_id": cid, "access_token": tok}, timeout=60)
    p.raise_for_status()
    pid = p.json()["id"]
    link = requests.get(f"{API}/{pid}", params={"fields": "permalink", "access_token": tok}, timeout=30).json().get("permalink")
    print("✅ 게시 완료:", pid, link)


if __name__ == "__main__":
    main()

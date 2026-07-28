#!/usr/bin/env python3
"""이슬(@ai_leeseul) 스레드 자동 게시.

AI 활용 팁·노하우를 존댓말 정보형으로 매일 저녁 1개 발행하고,
일부 글에는 스케일메이커 AI 강의로 향하는 담백한 CTA를 자연스럽게 얹는다.

- 요일(월~토)마다 큰 주제가 고정 배정되고, 날짜 시드로 세부 소재·형식이 매일 달라진다.
- 일요일은 쉼.
- 게시 전 이모지를 실제로 제거한다(프롬프트 지시 + strip_emoji 이중 안전장치).
"""

import argparse
import os
import random
import re
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
MODEL = "claude-opus-4-8"
THREADS_API = "https://graph.threads.net/v1.0"

# ─────────────────────────────────────────────────────────────
# 강의 홍보 설정 — ★ 여기만 고치면 홍보 문구가 바뀝니다 ★
#   스레드 관례상 본문에 raw URL을 넣지 않고 '프로필 링크'로 유도한다.
#   (실제 링크는 @ai_leeseul 계정 바이오에 걸어두면 됨)
# ─────────────────────────────────────────────────────────────
PROMO = {
    "brand": "스케일메이커",                 # 운영 주체/플랫폼
    "offer": "AI 마케팅 자동화 강의",        # 홍보할 대상(실제 강의명으로 교체 가능)
    "cta": "프로필 링크에서 확인해보세요",   # 마무리 유도 문구
}
# 전체 글 중 홍보 CTA를 얹는 비율. 나머지는 순수 정보/인사이트로 끝낸다.
# (너무 자주 홍보하면 팔로우·저장이 떨어지므로 낮게 유지)
PROMO_PROBABILITY = 0.30

# ─────────────────────────────────────────────────────────────
# 화자 설정
# ─────────────────────────────────────────────────────────────
PERSONA = """[화자: 이슬(@ai_leeseul)]
- AI로 마케팅을 자동화하는 걸 다루는 크리에이터이자 스케일메이커 대표.
- 블로그·SNS·광고·고객응대 같은 마케팅 업무를 AI로 자동화하는 법을
  '실무에서 진짜 쓰는 방식'으로 쉽게 풀어준다.
- 어렵게 가르치지 않는다. 바로 따라 할 수 있게, 담백하고 친절하게 알려준다.
- 이 계정은 'AI로 마케팅을 어떻게 자동화하는지'만 하나씩 알려주는 공간이다."""

SYSTEM_PROMPT = f"""당신은 스레드(Threads) 계정 '이슬(@ai_leeseul)'의 글을 대신 쓰는 사람입니다.
아래 화자가 되어, 오늘의 'AI 마케팅 자동화' 팁 하나를
'바로 써먹는 실무 정보'로 정리해 존댓말로 씁니다.
주제는 항상 마케팅 자동화(콘텐츠·SNS·광고·이미지영상·고객응대·데이터)로 한정합니다.

{PERSONA}

[말투·톤]
- 존댓말 정보형. "~해요", "~합니다", "~하시면 됩니다", "~더라고요"를 섞어 씁니다.
- 전문성은 있되 잘난 척하지 않습니다. 초보자도 이해할 쉬운 말로.
- 과장·단정 금지. "무조건", "100%", "누구나 월 천만원" 같은 표현 금지.
- 정보는 구체적으로. 두루뭉술한 원론 말고 실제로 해볼 수 있는 방법으로.

[글 형식 — 아래 구조를 지킵니다]
- [훅 1줄] : 공감되는 문제 상황이나 궁금증을 던진다. → 빈 줄
- [본문]  : 번호(1. 2. 3.)로 3~4개의 실전 팁/단계를 나열한다.
            각 번호 아래 1~2줄로 '왜/어떻게'를 구체적으로. 본문 안에는 빈 줄을 넣지 않는다.
            → 빈 줄
- [마무리 1줄] : 핵심을 한 번 더 짚거나, 가볍게 저장·의견을 유도한다.
- 글 전체 길이 200~450자. 해시태그 금지. 이모지·이모티콘 절대 금지(하나도 넣지 않음).
- 특정 유료도구를 '이거 사세요' 식으로 강매하지 않는다. 도구는 종류·용도로 소개한다.

[출력]
- 완성된 스레드 본문만 출력합니다. 따옴표나 설명, 머리말 없이 본문 그대로.
"""

# ─────────────────────────────────────────────────────────────
# 요일별 큰 주제(월=1 ... 토=6) + 세부 소재 풀. 전부 'AI 마케팅 자동화'로 한정.
# 날짜 시드로 매일 다른 소재를 고른다. 일요일(7)은 쉼.
# ─────────────────────────────────────────────────────────────
TOPICS = {
    1: {  # 월 — 콘텐츠 마케팅 자동화
        "name": "콘텐츠 마케팅 자동화 (블로그·SNS 글)",
        "subs": [
            "블로그 글 한 편을 AI로 30분 만에 잡는 흐름",
            "소재 하나로 블로그·인스타·스레드 글을 한 번에 뽑기",
            "매주 올릴 콘텐츠 주제를 AI로 대량으로 뽑는 법",
            "우리 브랜드 말투를 AI에 학습시켜 일관되게 쓰는 법",
            "후기·댓글을 콘텐츠 소재로 자동 재활용하는 법",
            "AI 티 안 나게 마케팅 글을 다듬는 방법",
        ],
    },
    2: {  # 화 — SNS 운영·발행 자동화
        "name": "SNS 운영·발행 자동화",
        "subs": [
            "SNS 게시물을 미리 만들어 예약 발행하는 흐름",
            "한 콘텐츠를 채널별 형식으로 자동 변환하는 법",
            "해시태그·캡션을 AI로 빠르게 뽑는 방법",
            "매일 올릴 게시를 자동으로 돌리는 파이프라인 개념",
            "콘텐츠 캘린더를 AI로 한 달치 짜는 법",
            "반복되는 SNS 운영 업무 중 자동화할 것 고르기",
        ],
    },
    3: {  # 수 — 광고 카피·소재 자동 생성
        "name": "광고 카피·소재 자동 생성",
        "subs": [
            "같은 상품으로 광고 카피 10개를 뽑아 비교하기",
            "타깃별로 광고 문구 톤을 바꿔 뽑는 법",
            "후킹되는 첫 문장을 AI로 여러 개 만드는 방법",
            "상세페이지 카피를 구조 잡아 자동으로 쓰는 법",
            "경쟁사 소구점을 정리해 우리 카피에 반영하는 법",
            "광고 소재 아이디어가 막혔을 때 AI로 뚫는 법",
        ],
    },
    4: {  # 목 — 마케팅 이미지·영상 자동 제작
        "name": "마케팅 이미지·영상 자동 제작",
        "subs": [
            "상세페이지·SNS용 이미지를 AI로 만드는 법",
            "제품 사진을 감성 광고 컷으로 바꾸는 법",
            "짧은 홍보 영상을 장비 없이 AI로 만드는 흐름",
            "썸네일 여러 버전을 AI로 빠르게 뽑아 고르기",
            "AI 목소리·자막으로 영상 제작 품을 줄이기",
            "배경 제거·보정을 자동으로 처리하는 도구",
        ],
    },
    5: {  # 금 — 고객 응대·DM·챗봇 자동화
        "name": "고객 응대·DM·챗봇 자동화",
        "subs": [
            "자주 오는 문의를 AI로 반자동 응대하는 법",
            "DM·댓글 응대 템플릿을 AI로 만들어 두기",
            "예약·주문 문의를 챗봇으로 받는 흐름 개념",
            "고객 후기에 답글을 빠르게 다는 자동화",
            "FAQ를 정리해 AI 응대에 물려두는 법",
            "응대 자동화에서 사람이 꼭 개입해야 할 지점",
        ],
    },
    6: {  # 토 — 마케팅 데이터·리포트 자동화
        "name": "마케팅 데이터·리포트 자동화",
        "subs": [
            "광고·SNS 성과를 AI로 요약 리포트 만드는 법",
            "엑셀 마케팅 데이터를 말로 시켜 정리하는 법",
            "어떤 콘텐츠가 잘 됐는지 AI로 분석하는 흐름",
            "리드(문의 고객) 목록을 자동으로 분류하는 법",
            "월간 마케팅 리포트를 반자동으로 만드는 순서",
            "숫자만 보고 다음 액션을 AI에게 제안받는 법",
        ],
    },
}

# 주제별 홍보 CTA 가중치(강의와 연결이 자연스러운 주제일수록 높게).
PROMO_WEIGHT = {1: 1.0, 2: 1.0, 3: 1.0, 4: 0.9, 5: 1.0, 6: 1.1}


def build_user_message(topic: dict, today: datetime, topic_id: int) -> tuple[str, bool, str]:
    """그날의 세부 소재와 홍보 여부를 시드로 정해 유저 메시지를 만든다."""
    seed = int(today.strftime("%Y%m%d"))
    rng = random.Random(seed)
    sub = rng.choice(topic["subs"])

    # 홍보 CTA를 얹을지 결정 (주제 가중치 반영)
    use_promo = rng.random() < min(PROMO_PROBABILITY * PROMO_WEIGHT.get(topic_id, 1.0), 0.6)

    promo_line = ""
    if use_promo:
        promo_line = (
            "\n\n[이번 글은 마무리에 담백한 홍보 한 줄을 자연스럽게 얹습니다]\n"
            f"- 본문(정보)은 그대로 충실히 쓰고, 맨 마지막 줄에서만 "
            f"'{PROMO['brand']}의 {PROMO['offer']}'를 슬쩍 언급하며 "
            f"'{PROMO['cta']}' 같은 뉘앙스로 부드럽게 유도하세요.\n"
            "- 강매·과장 금지. '더 깊게 배우고 싶으시면' 정도의 톤으로, 한 줄이면 충분합니다.\n"
            "- raw URL은 쓰지 말고 '프로필 링크'로만 안내합니다."
        )

    user_message = (
        f"오늘의 큰 주제: {topic['name']}\n"
        f"오늘 다룰 구체적 소재: {sub}\n\n"
        "위 소재로 오늘의 'AI 마케팅 자동화' 팁 글 한 편을 존댓말 정보형으로 써주세요. "
        "반드시 마케팅 자동화 맥락(마케터·1인 사업자·브랜드 운영자가 써먹는 관점)으로 씁니다. "
        "구조(훅 1줄 → 빈 줄 → 번호형 본문 3~4개 → 빈 줄 → 마무리 1줄)와 "
        "규칙(200~450자, 해시태그 없음, 이모지 절대 금지, 과장·단정 금지)을 지키세요. "
        "번호 항목은 실제로 따라 할 수 있게 구체적으로 적고, 어려운 용어는 풀어서 설명하세요."
        f"{promo_line}"
    )
    return sub, use_promo, user_message


# 이모지/기호 유니코드 블록. 프롬프트로 금지해도 모델이 가끔 흘리므로 발행 직전에 실제로 걷어낸다.
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002190-\U000021FF"
    "\U00002B00-\U00002BFF"
    "\U0000FE00-\U0000FE0F"
    "\U0001F000-\U0001F0FF"
    "\U0000203C\U00002049"
    "\U000024C2\U00003030\U0000303D\U00003297\U00003299"
    "\U000000A9\U000000AE\U00002122"
    "\U0000200D"
    "]+"
)


def strip_emoji(text: str) -> str:
    """이모지를 제거하고 군더더기 공백을 정리한다. (번호·마침표 등 텍스트는 보존)"""
    cleaned = _EMOJI_RE.sub("", text)
    lines = [line.rstrip() for line in cleaned.split("\n")]
    lines = [line.lstrip() if line.strip() else "" for line in lines]
    return "\n".join(re.sub(r"[ \t]{2,}", " ", line) for line in lines).strip()


def generate_post(user_message: str) -> str:
    """Claude로 글을 생성한다. (API 키 없으면 예외)"""
    import anthropic

    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY 자동 사용
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    text = next((b.text for b in response.content if b.type == "text"), "").strip()
    if not text:
        sys.exit("[오류] Claude 응답에서 본문 텍스트를 찾지 못했습니다.")
    return strip_emoji(text)


def post_to_threads(user_id: str, access_token: str, text: str) -> str:
    """Threads 컨테이너 생성 → 30초 대기 → 발행. 게시물 ID 반환."""
    import requests

    create = requests.post(
        f"{THREADS_API}/{user_id}/threads",
        json={"media_type": "TEXT", "text": text, "access_token": access_token},
        timeout=30,
    )
    create.raise_for_status()
    creation_id = create.json()["id"]

    time.sleep(30)  # Threads 권장 대기

    publish = requests.post(
        f"{THREADS_API}/{user_id}/threads_publish",
        json={"creation_id": creation_id, "access_token": access_token},
        timeout=30,
    )
    publish.raise_for_status()
    return publish.json()["id"]


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"[오류] 환경변수 {name} 가 설정되지 않았습니다.")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="이슬(@ai_leeseul) 스레드 AI 팁 자동 게시")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="게시하지 않고 생성된 글만 출력한다 (검증용).",
    )
    args = parser.parse_args()

    now = datetime.now(KST)
    weekday = now.isoweekday()  # 월=1 ... 일=7
    topic = TOPICS.get(weekday)
    if topic is None:
        print(f"오늘({now:%Y-%m-%d %A})은 게시일이 아닙니다(일요일 쉼). 종료합니다.")
        return

    sub, use_promo, user_message = build_user_message(topic, now, weekday)
    print(
        f"[{now:%Y-%m-%d %H:%M KST}] 주제: {topic['name']} / 소재: {sub} "
        f"/ 홍보: {'O' if use_promo else 'X'}"
    )

    # 게시 모드에서만 토큰을 요구한다. (dry-run은 API 키만 있으면 됨)
    if not args.dry_run:
        require_env("ANTHROPIC_API_KEY")
        user_id = require_env("THREADS_USER_ID")
        access_token = require_env("THREADS_ACCESS_TOKEN")

    text = generate_post(user_message)
    print("=== 생성된 글 ===")
    print(text)
    print(f"=== 글자 수: {len(text)}자 ===")

    if args.dry_run:
        print("(dry-run) 게시하지 않고 종료합니다.")
        return

    post_id = post_to_threads(user_id, access_token, text)
    print(f"게시 완료. Threads 게시물 ID: {post_id}")


if __name__ == "__main__":
    main()

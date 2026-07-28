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
    "offer": "AI 실무 활용 강의",            # 홍보할 대상(강의명으로 교체 가능)
    "cta": "프로필 링크에서 확인해보세요",   # 마무리 유도 문구
}
# 전체 글 중 홍보 CTA를 얹는 비율. 나머지는 순수 정보/인사이트로 끝낸다.
# (너무 자주 홍보하면 팔로우·저장이 떨어지므로 낮게 유지)
PROMO_PROBABILITY = 0.30

# ─────────────────────────────────────────────────────────────
# 화자 설정
# ─────────────────────────────────────────────────────────────
PERSONA = """[화자: 이슬(@ai_leeseul)]
- AI·생산성 콘텐츠를 다루는 크리에이터이자 스케일메이커 대표.
- 최신 AI 도구와 활용법을 '실무에서 진짜 쓰는 방식'으로 쉽게 풀어준다.
- 어렵게 가르치지 않는다. 바로 따라 할 수 있게, 담백하고 친절하게 알려준다.
- 이 계정은 'AI를 일과 콘텐츠에 어떻게 써먹는지'를 하나씩 알려주는 공간이다."""

SYSTEM_PROMPT = f"""당신은 스레드(Threads) 계정 '이슬(@ai_leeseul)'의 글을 대신 쓰는 사람입니다.
아래 화자가 되어, 오늘의 AI 활용 팁·노하우 하나를
'바로 써먹는 실무 정보'로 정리해 존댓말로 씁니다.

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
# 요일별 큰 주제(월=1 ... 토=6) + 세부 소재 풀.
# 날짜 시드로 매일 다른 소재를 고른다. 일요일(7)은 쉼.
# ─────────────────────────────────────────────────────────────
TOPICS = {
    1: {  # 월 — 프롬프트 노하우
        "name": "ChatGPT·Claude 프롬프트 노하우",
        "subs": [
            "원하는 답이 안 나올 때 프롬프트를 고치는 법",
            "역할을 부여해 답변 품질을 끌어올리는 방법",
            "예시를 넣어 원하는 형식으로 뽑아내는 법",
            "긴 작업을 단계로 쪼개 시키는 프롬프트 설계",
            "AI가 지어내지 않게 만드는 지시 방법",
            "한 번에 끝내는 대신 되묻게 만드는 프롬프트",
        ],
    },
    2: {  # 화 — 글쓰기·콘텐츠
        "name": "AI 글쓰기·콘텐츠 자동화",
        "subs": [
            "블로그 글 초안을 30분 만에 잡는 흐름",
            "AI 티 안 나게 문장을 다듬는 방법",
            "하나의 소재로 여러 채널 글을 뽑는 법",
            "제목·훅을 여러 개 뽑아 고르는 방법",
            "내 말투를 AI에게 학습시키는 방법",
            "댓글·후기를 콘텐츠로 재활용하는 법",
        ],
    },
    3: {  # 수 — 업무 생산성
        "name": "AI 업무 생산성·자동화",
        "subs": [
            "매일 반복하는 일을 AI로 줄이는 첫 단계",
            "회의록·메일을 AI로 정리하는 흐름",
            "엑셀·데이터 정리를 말로 시키는 법",
            "자료 조사 시간을 반으로 줄이는 방법",
            "할 일 정리와 우선순위를 AI로 잡기",
            "AI를 붙여 자동화할 업무를 고르는 기준",
        ],
    },
    4: {  # 목 — 이미지·영상 툴
        "name": "AI 이미지·영상 툴 활용",
        "subs": [
            "썸네일·상세페이지 이미지를 AI로 만드는 법",
            "사진 배경 제거·보정을 빠르게 하는 도구",
            "짧은 홍보 영상을 AI로 만드는 흐름",
            "AI 목소리·자막으로 영상 품을 줄이기",
            "제품 사진을 감성 컷으로 바꾸는 법",
            "무료로 쓸 만한 AI 이미지 도구 고르기",
        ],
    },
    5: {  # 금 — AI로 일·수익
        "name": "AI로 일·수익 만들기",
        "subs": [
            "AI로 부업 콘텐츠를 시작하는 현실적인 순서",
            "1인 사업자가 AI로 인건비를 아끼는 지점",
            "AI로 마케팅 카피를 빠르게 뽑는 법",
            "고객 문의 응대를 AI로 반자동화하기",
            "작은 자동화 하나로 시간을 버는 사례",
            "AI 도구값이 아깝지 않게 쓰는 기준",
        ],
    },
    6: {  # 토 — 입문자 기초
        "name": "AI 입문자를 위한 기초",
        "subs": [
            "AI 처음 시작할 때 딱 3가지만 하기",
            "초보가 가장 많이 하는 프롬프트 실수",
            "무료로 시작해도 되는 이유와 한계",
            "AI를 믿으면 안 되는 순간 구분하기",
            "어떤 일에 AI를 쓰고 어떤 일은 직접 할지",
            "AI 용어, 이것만 알면 시작할 수 있어요",
        ],
    },
}

# 주제별 홍보 CTA 가중치(강의와 연결이 자연스러운 주제일수록 높게).
PROMO_WEIGHT = {1: 1.0, 2: 1.0, 3: 0.9, 4: 0.8, 5: 1.2, 6: 1.1}


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
        "위 소재로 오늘의 AI 활용 팁 글 한 편을 존댓말 정보형으로 써주세요. "
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

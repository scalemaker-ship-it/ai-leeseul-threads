# 이슬(@ai_leeseul) 스레드 자동화

AI 활용 팁·노하우를 **존댓말 정보형**으로 매일 저녁 1개 발행하고,
일부 글에는 **스케일메이커 AI 강의**로 향하는 담백한 CTA를 자연스럽게 얹는 자동화입니다.

> 오산·빵찌·0ra 자동화와 **완전히 분리된 별도 저장소·Meta 앱·계정**입니다.

## 구조

| 파일 | 역할 |
|---|---|
| `threads_post.py` | 요일로 주제 선택 → 날짜 시드로 소재·홍보 여부 결정 → Claude 생성 → 이모지 제거 → Threads 게시 |
| `.github/workflows/threads-daily.yml` | **하루 1회**(저녁) 크론, 랜덤 지연 포함 |
| `docs/글쓰기_가이드.md` | 톤·구조·금지 규칙 |
| `requirements.txt` | anthropic, requests |

### 발행 스케줄 — 하루 1회 (월~토, 일요일 쉼)

| 크론(UTC) | 목표 게시(KST) | 성격 |
|---|---|---|
| `0 11 * * 1-6` | 20:00 + 랜덤 0~60분 → **20:00~21:00** | 하루를 마무리하는 저녁 노출 |

> 크론을 목표(21시)보다 1시간 앞선 20:00 KST에 둔 이유: GitHub 무료 러너의 스케줄
> 크론은 혼잡 시 늦게 뜨는데, **자정을 넘기면 일요일로 넘어가 스킵**됩니다.
> 앞당겨 두고 랜덤 지연으로 분산해 같은 날 안에 발행되게 합니다.

### 요일별 주제 (날짜 시드로 세부 소재 매일 변경)

| 요일 | 주제 |
|---|---|
| 월 | ChatGPT·Claude 프롬프트 노하우 |
| 화 | AI 글쓰기·콘텐츠 자동화 |
| 수 | AI 업무 생산성·자동화 |
| 목 | AI 이미지·영상 툴 활용 |
| 금 | AI로 일·수익 만들기 |
| 토 | AI 입문자를 위한 기초 |

각 요일마다 6개의 세부 소재 풀이 있고, 날짜를 시드로 하나를 고릅니다.
같은 날 재실행해도 같은 글이 나와 중복 발행이 방지됩니다.

## 강의 홍보 설정 — ★ 여기만 고치면 됩니다 ★

`threads_post.py` 상단 `PROMO` 딕셔너리:

```python
PROMO = {
    "brand": "스케일메이커",              # 운영 주체/플랫폼
    "offer": "AI 실무 활용 강의",         # ← 실제 강의명으로 교체
    "cta":   "프로필 링크에서 확인해보세요",
}
PROMO_PROBABILITY = 0.30                  # 홍보 CTA를 얹는 글 비율
```

- 스레드 관례상 본문에 **raw URL을 넣지 않고 '프로필 링크'로 유도**합니다.
  실제 강의 링크는 **@ai_leeseul 계정 바이오**에 걸어두세요.
- 전체 글의 약 30%에만 CTA가 붙고, 나머지는 순수 정보로 끝납니다(과홍보 방지).

## 로컬 미리보기 (게시 없이 글만 확인)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...      # 토큰 없이 API 키만 있으면 됨
python threads_post.py --dry-run  # 오늘 요일 기준으로 생성
```

## 현재 상태 — 발행 대기 (2026-07-29)

| 항목 | 상태 |
|---|---|
| 코드·워크플로우·문서 | ✅ |
| 글 생성 (dry-run 검증) | ✅ 존댓말·번호형·이모지0, 홍보 버전 포함 |
| 저장소 `scalemaker-ship-it/ai-leeseul-threads` | ✅ 생성·푸시 |
| `ANTHROPIC_API_KEY` 시크릿 | ✅ |
| `THREADS_USER_ID` (`27379182415114797`) / `THREADS_ACCESS_TOKEN` 시크릿 | ✅ **등록 완료** |
| 실제 첫 발행 | ⏳ 미실행 (다음 저녁 크론에 자동, 또는 수동 트리거) |

**세팅 완료 — 다음 저녁 크론(월~토 20:00~21:00 KST)에 자동으로 첫 글이 올라갑니다.**
즉시 테스트하려면: Actions 탭 → **Run workflow**(dry_run 체크 해제) 또는
`gh workflow run threads-daily.yml --repo scalemaker-ship-it/ai-leeseul-threads`.

### Meta 앱 정보 (토큰 재발급 시 참고)

- 앱 이름: **이슬_자동화**, 앱 ID `1327618752693437`, Threads 앱 ID `1401596085180537`
- `@ai_leeseul` = Threads 테스터(수락 완료). 권한 `threads_basic` + `threads_content_publish`.
- 토큰은 약 60일 후 만료. 재발급 절차는 `빵찌스레드자동화/README.md`와 동일
  (토큰 생성기 버튼의 `window.open` 후킹 → authorize URL 가로채 같은 탭에서 열기
  → 콜백 페이지 HTML에서 토큰 추출). USER_ID 재확인:
  ```bash
  curl -s "https://graph.threads.net/v1.0/me?fields=id,username&access_token=<토큰>"
  gh secret set THREADS_ACCESS_TOKEN --repo scalemaker-ship-it/ai-leeseul-threads
  ```

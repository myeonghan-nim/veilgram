# VeilGram

> 이 프로젝트는 ChatGPT를 사용하여 작성된 VibeCoding 프로젝트입니다.

VeilGram는 이메일이나 전화번호 없이 익명 ID로 가입할 수 있는 익명 SNS 플랫폼입니다.<br/>
텍스트, 이미지(JPEG/PNG), 동영상(MP4) 등 멀티미디어 업로드와 최대 5개 선택지의 실시간 집계형 투표 기능을 제공해 사용자가 자유롭게 소통할 수 있도록 설계되었습니다.<br/>

## 1. 주요 기능

- **익명 프로필 생성**<br/>
  이메일·전화번호 없이 익명 ID로 가입 가능<br/>
- **닉네임 관리**<br/>
  닉네임 설정·변경, 중복 검사 및 차단어 필터링<br/>
- **멀티미디어 업로드**<br/>
  텍스트, 이미지, 동영상 업로드 지원<br/>
- **투표 기능**<br/>
  최대 5개 선택지 투표 생성 및 실시간 집계<br/>
- **실시간 피드 업데이트**<br/>
  WebSocket 또는 SSE 기반 실시간 반영<br/>
- **소셜 상호작용**<br/>
  좋아요, 댓글(신고 포함), 리그램(공유), 팔로우/언팔로우<br/>
- **탐색 및 검색**<br/>
  Discover 탭, 해시태그·위치 태그 자동 인식, 사용자 및 키워드 검색<br/>
- **콘텐츠 모더레이션**<br/>
  익명 신고 기능, NSFW·욕설·스팸 키워드 자동 필터링<br/>

## 2. 비기능 요구사항 하이라이트

- **확장성**<br/>
  오토스케일링, DB 샤딩 및 파티셔닝, 마이크로서비스 아키텍처 지원<br/>
- **성능**<br/>
  P99 응답시간 <100ms, CDN 및 Redis 기반 캐싱<br/>
- **가용성**<br/>
  SLA 99.9%, 멀티 리전 배포, 블루/그린 및 카나리 배포 전략<br/>
- **신뢰성**<br/>
  회로 차단기 패턴, Kubernetes 프로브 및 자동 복구<br/>
- **데이터 일관성**<br/>
  피드·알림 시스템은 최종 일관성, 계정·트랜잭션은 강한 일관성 보장<br/>
- **보안 및 프라이버시**<br/>
  TLS 및 디스크 암호화, API 레이트 리밋, JWT 인증, 익명화된 IP/기기 로그, 90일 데이터 보존 정책<br/>
- **운영 및 모니터링**<br/>
  ELK/EFK 로그 분석, Prometheus/Grafana 지표 수집 및 경고<br/>
- **CI/CD**<br/>
  pytest, 린트, 보안 스캔 자동 테스트, GitOps 기반 자동 배포<br/>

## 3. API Documentation

- Swagger UI: `/api/docs/`
- ReDoc: `/api/redoc/`
- OpenAPI Schema(JSON): `/api/schema/`

### 1. Export OpenAPI file

```bash
python manage.py spectacular --file openapi.yaml
python manage.py spectacular --format openapi-json --file openapi.json
```

### 2. Quick examples

#### 1. Auth

- Use JWT bearer tokens

```
Authorization: Bearer <access_token>
```

#### 2. Create Post

- Endpoint: `POST /api/v1/posts/`

- Request Body:

```json
{
  "content": "오늘 점심 뭐먹지? #점심",
  "asset_ids": ["11111111-1111-1111-1111-111111111111"],
  "poll": {"options": ["국밥", "비빔밥"], "allow_multiple": false}
}
```

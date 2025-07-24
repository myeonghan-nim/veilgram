# 시퀀스 다이어그램

## 1. 개요

### 1. 목적

시퀀스 다이어그램은 시스템의 동작을 순서대로 나타내는 다이어그램으로 각 객체 간의 상호작용을 시각적으로 표현합니다. 여기서는 VeilGram 서비스의 주요 기능에 대한 시퀀스 다이어그램을 작성하여 시스템의 흐름과 상호작용을 명확히 합니다.

## 2. 주요 기능

### 1. 사용자 관리

#### 1. 회원가입

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth Service(JWT)
    participant DB as PostgreSQL(Auth/Profile)
    participant Bus as Message Bus(Kafka/RabbitMQ/Redis)

    Client->>APIGW: POST /api/v1/auth/signup
    APIGW->>Auth: 회원가입 요청
    Auth->>DB: INSERT INTO users (uuid, created_at)
    DB-->>Auth: 201 Created
    Auth->>Auth: JWT Access/Refresh 토큰 생성
    Auth->>Bus: publish UserRegistered 이벤트
    Auth-->>APIGW: 201 Created + { access_token, refresh_token }
    APIGW-->>Client: 회원가입 결과 반환
```

#### 2. 로그인

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth Service(JWT)
    participant DB as PostgreSQL(Auth/Profile)
    participant Bus as Message Bus(Kafka/RabbitMQ/Redis)

    Client->>APIGW: POST /api/v1/auth/login (body: { key })
    APIGW->>Auth: 로그인 요청
    Auth->>DB: SELECT * FROM users WHERE uuid = key.sub
    alt 사용자 검증 성공
        DB-->>Auth: 사용자 레코드
        Auth->>Auth: JWT Access/Refresh 토큰 생성
        Auth->>Bus: publish UserLoggedIn 이벤트
        Auth-->>APIGW: 200 OK + { access_token, refresh_token }
    else 사용자 검증 실패
        Auth-->>APIGW: 401 Unauthorized + { error: "Invalid Key" }
    end
    APIGW-->>Client: 로그인 결과 반환
```

#### 3. 동시 로그인 제한

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth Service(JWT)
    participant SessionCache as Redis Cache(SessionStore)
    participant DB as PostgreSQL(Auth/Profile)
    participant Bus as Message Bus(Kafka/RabbitMQ/Redis)

    Client->>APIGW: POST /api/v1/auth/login (body: { key, device_id })
    APIGW->>Auth: 로그인 요청
    Auth->>SessionCache: GET sessions:{key.sub}
    SessionCache-->>Auth: 기존 세션 있음 여부 확인
    opt 다른 디바이스에서 이미 로그인됨
        Auth->>SessionCache: DEL sessions:{key.sub}
        Auth->>Bus: publish SessionRevoked 이벤트
    end
    Auth->>DB: SELECT * FROM users WHERE uuid = key.sub
    alt 사용자 검증 성공
        DB-->>Auth: 사용자 레코드
        Auth->>Auth: JWT Access/Refresh 토큰 생성
        Auth->>Bus: publish UserLoggedIn 이벤트
        Auth-->>APIGW: 200 OK + { access_token, refresh_token }
    else 사용자 검증 실패
        Auth-->>APIGW: 401 Unauthorized + { error: "Invalid Key" }
    end
    APIGW-->>Client: 로그인 결과 반환
```

#### 4. 회원 탈퇴

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth Service(JWT)
    participant SessionCache as Redis Cache(SessionStore)
    participant DB as PostgreSQL(Auth/Profile)
    participant Bus as Message Bus(Kafka/RabbitMQ/Redis)
    participant User as User Service(Profile)
    participant Post as Post Service
    participant Comment as Comment Service
    participant Media as Media Service
    participant Poll as Poll Service
    participant Search as Search Service
    participant Storage as MinIO + Varnish
    participant RedisCtr as Redis Cache(VoteCounters)
    participant OpenSearch as OpenSearch Cluster(Search Index)

    Client->>APIGW: DELETE /api/v1/auth/unregister (body: { key })
    APIGW->>Auth: 탈퇴 요청
    Auth->>DB: SELECT * FROM users WHERE uuid = key.sub
    alt 사용자 검증 성공
        DB-->>Auth: 사용자 레코드
        opt 세션 정보 삭제
            Auth->>SessionCache: DEL sessions:{key.sub}
        end
        Auth->>Bus: publish UserDeleted 이벤트
        Auth-->>APIGW: 204 No Content
        par 서비스별 데이터 삭제
            Bus->>User: UserDeleted 이벤트
            User->>DB: DELETE FROM users WHERE uuid = key.sub
        and
            Bus->>Post: UserDeleted 이벤트
            Post->>DBPosts: DELETE FROM posts WHERE author_id = key.sub
        and
            Bus->>Comment: UserDeleted 이벤트
            Comment->>DBComments: DELETE FROM comments WHERE user_id = key.sub
        and
            Bus->>Media: UserDeleted 이벤트
            Media->>Storage: DELETE objects for user key.sub
        and
            Bus->>Poll: UserDeleted 이벤트
            Poll->>RedisCtr: DEL vote counters for user key.sub
        and
            Bus->>Search: UserDeleted 이벤트
            Search->>OpenSearch: DELETE index entries for user key.sub
        end
    else 사용자 검증 실패
        Auth-->>APIGW: 401 Unauthorized + { error: "Invalid Key" }
    end
    APIGW-->>Client: 탈퇴 결과 반환
```

#### 5. 비활성 계정 관리

```mermaid
sequenceDiagram
    participant Scheduler as Scheduler (Celery Beat)
    participant User as User Service (Profile)
    participant DB as PostgreSQL (Auth/Profile)
    participant Auth as Auth Service (JWT)
    participant SessionCache as Redis Cache (SessionStore)
    participant Bus as Message Bus (Kafka/RabbitMQ/Redis)
    participant Post as Post Service
    participant Comment as Comment Service
    participant Media as Media Service
    participant Poll as Poll Service
    participant Search as Search Service

    Scheduler->>User: 비화설 계정 삭제 트리거
    User->>DB: SELECT uuid FROM users WHERE last_active ≤ now() – retention_period
    DB-->>User: 해당되는 계정 목록 반환
    alt 계정 존재
        loop for each 계정
            User->>Auth: 계정 세션 삭제 요청
            Auth->>SessionCache: DEL sessions:{user_id}
            Auth->>Bus: publish UserSessionRevoked (user_id)
            User->>DB: DELETE FROM users WHERE user.id = user_id
            DB-->>User: 204 No Content
            User->>Bus: publish UserDeleted (user_id)
        end
        par 서비스별 데이터 삭제
            Bus->>Post: UserDeleted event
            Post->>DB: DELETE FROM posts WHERE author_id = user_id
        and
            Bus->>Comment: UserDeleted event
            Comment->>DB: DELETE FROM comments WHERE user_id = user_id
        and
            Bus->>Media: UserDeleted event
            Media->>Storage: DELETE objects for user user_id
        and
            Bus->>Poll: UserDeleted event
            Poll->>RedisCounters: DEL vote counters for user user_id
        and
            Bus->>Search: UserDeleted event
            Search->>OpenSearch: DELETE index entries for user user_id
        end
    else 계정 없음
        User-->>Scheduler: 204 No Content
    end
```

#### 6. 프로필 관리

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant DB as PostgreSQL(Profile)
    participant Auth as Auth
    participant User as User
    participant DB as PostgreSQL(Auth/Profile)
    participant Cache as Redis Cache(FilterRules)
    participant Bus as Message Bus(Kafka/RabbitMQ/Redis)

    Client->>APIGW: POST /api/v1/profile (body: { nickname })
    APIGW->>Auth: JWT 검증
    alt 인증 헤더 포함
        Auth-->>DB: SELECT * FROM users WHERE uuid = key.sub
        alt 사용자 존재
            DB-->>Auth: 사용자 레코드
        else 사용자 없음
            Auth-->>APIGW: 401 Unauthorized + { error: "Invalid Key" }
            APIGW-->>Client: 401 Unauthorized + { error: "Authentication Required" }
        end
    else 인증 헤더 없음
        APIGW-->>Client: 401 Unauthorized + { error: "Authentication Required" }
    end
    APIGW->>User: 프로필 생성 요청
    User->>DB: SELECT count(*) FROM profiles WHERE nickname = 요청닉네임
    DB-->>User: 중복 개수 반환
    User->>Cache: GET forbidden_words_list
    Cache-->>User: 차단어 목록 반환
    alt 닉네임 중복 또는 차단어 포함
        User-->>APIGW: 400 Bad Request + { error: "invalid nickname" }
    else 닉네임 유효
        User->>DB: INSERT INTO profiles (user_id, nickname) VALUES (...)
        DB-->>User: 201 Created + 프로필 정보
        User->>Bus: publish ProfileCreated 이벤트
        User-->>APIGW: 201 Created + { profile }
    end
    APIGW-->>Client: 프로필 생성 결과 반환
```

#### 7. 프로필 조회

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant User as User
    participant DB as PostgreSQL(Auth/Profile)

    Client->>APIGW: GET /api/v1/profile/{user_id}
    APIGW->>Auth: JWT 검증
    alt 인증 성공
        Auth-->>APIGW: 200 OK
        APIGW->>User: 프로필 조회 요청
        User->>DB: SELECT * FROM profiles WHERE user_id = {user_id}
        DB-->>User: 프로필 데이터 반환
        alt 프로필 존재
            User->>DB: SELECT COUNT(*) FROM follows WHERE following_id = {user_id}
            DB-->>User: 팔로워 수
            User->>DB: SELECT COUNT(*) FROM follows WHERE follower_id = {user_id}
            DB-->>User: 팔로잉 수
            User-->>APIGW: 200 OK + { profile, follower_count, following_count }
        else 프로필 없음
            User-->>APIGW: 404 Not Found + { error: "Profile Not Found" }
        end
    else 인증 실패
        Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
    end
    APIGW-->>Client: 응답 반환
```

#### 8. 팔로우/언팔로우

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant User as User
    participant DB as PostgreSQL(Auth/Profile)
    participant Bus as Message Bus(Kafka/RabbitMQ/Redis)
    participant Notification as Notification

    alt 팔로우 요청
        Client->>APIGW: POST /api/v1/follow{target_user_id}
        APIGW->>Auth: JWT 검증
        alt 인증 실패
            Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
        else 인증 성공
            APIGW->>User: 팔로우 요청
            User->>DB: SELECT COUNT(*) FROM follows WHERE follower_id = 요청자 AND following_id = 대상
            DB-->>User: 중복 여부 반환
            alt 중복 없음
                User->>DB: INSERT INTO follows(follower_id, following_id)
                DB-->>User: 201 Created
                User->>Bus: publish UserFollowed 이벤트
                Bus->>Notification: UserFollowed 이벤트
                Notification->>Notification: 푸시 알림 전송
                User-->>APIGW: 204 No Content
            else 이미 팔로우 중
                User-->>APIGW: 400 Bad Request + { error: "Already following" }
            end
        end
    else 언팔로우 요청
        Client->>APIGW: DELETE /api/v1/follow/{target_user_id}
        APIGW->>Auth: JWT 검증
        alt 인증 실패
            Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
        else 인증 성공
            APIGW->>User: 언팔로우 요청
            User->>DB: SELECT COUNT(*) FROM follows WHERE follower_id = 요청자 AND following_id = 대상
            DB-->>User: 관계 여부 반환
            alt 관계 존재
                User->>DB: DELETE FROM follows WHERE follower_id = 요청자 AND following_id = 대상
                DB-->>User: 204 No Content
                User->>Bus: publish UserUnfollowed 이벤트
                Bus->>Notification: UserUnfollowed 이벤트
                Notification->>Notification: 알림 취소 처리
                User-->>APIGW: 204 No Content
            else 팔로우 관계 없음
                User-->>APIGW: 400 Bad Request + { error: "Not following" }
            end
        end
    end
    APIGW-->>Client: 요청 결과 반환
```

#### 9. 사용자 차단

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant Feed as Feed
    participant Comment as Comment
    participant Redis as Redis Cache(BlockList)
    participant Cassandra as Cassandra(Feed)
    participant DB as PostgreSQL(Profile)

    opt 피드 조회
        Client->>APIGW: GET /api/v1/feed
        APIGW->>Auth: JWT 검증
        alt 인증 실패
            Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
        else 인증 성공
            APIGW->>Feed: 피드 조회 요청
            Feed->>Redis: GET blocks:{user_id}
            Redis-->>Feed: 차단된 사용자 목록
            Feed->>Cassandra: 게시물 조회 (author_id NOT IN blocks)
            Cassandra-->>Feed: 게시물 목록
            Feed-->>APIGW: 피드 반환
        end
    end
    opt 댓글 조회
        Client->>APIGW: GET /api/v1/posts/{post_id}/comments
        APIGW->>Auth: JWT 검증
        alt 인증 실패
            Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
        else 인증 성공
            APIGW->>Comment: 댓글 조회 요청
            Comment->>Redis: GET blocks:{user_id}
            Redis-->>Comment: 차단된 사용자 목록
            Comment->>DB: 댓글 조회 (post_id, user_id NOT IN blocks)
            DB-->>Comment: 댓글 목록
            Comment-->>APIGW: 댓글 반환
        end
    end
    APIGW-->>Client: 응답 반환
```

#### 10. 사용자 통계

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant User as User
    participant DB as PostgreSQL(Auth/Profile)

    Client->>APIGW: GET /api/v1/profile/{user_id}/stats
    APIGW->>Auth: JWT 검증
    alt 인증 실패
        Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
    else 인증 성공
        APIGW->>User: 활동 통계 요청
        User->>DB: SELECT COUNT(*) FROM posts WHERE author_id = {user_id}
        DB-->>User: 게시물 수
        User->>DB: SELECT COUNT(*) FROM follows WHERE following_id = {user_id}
        DB-->>User: 팔로워 수
        User-->>APIGW: 200 OK + { post_count, follower_count }
    end
    APIGW-->>Client: 통계 반환
```

#### 11. 사용자 활동 로그

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant Post as Post
    participant Bus as Message Bus(Kafka/RabbitMQ/Redis)
    participant Audit as Audit

    opt 로그인 활동
        Client->>APIGW: POST /api/v1/auth/login (body: { key, device_id })
        APIGW->>Auth: 로그인 요청
        Auth->>Auth: 토큰 생성
        Auth->>Bus: UserLoggedIn 이벤트 발행
        Auth->>Audit: 로그인 활동 로그 기록
        Auth-->>APIGW: 200 OK + { access_token, refresh_token }
    end
    opt 게시물 작성 활동
        Client->>APIGW: POST /api/v1/posts (body: { content, media, poll })
        APIGW->>Auth: JWT 검증
        APIGW->>Post: 게시물 작성 요청
        Post->>Post: 미디어·투표 처리
        Post->>Bus: PostCreated 이벤트 발행
        Post->>Audit: 게시물 작성 활동 로그 기록
        Post-->>APIGW: 201 Created + { post_id }
    end
    APIGW-->>Client: 요청 결과 반환
```

#### 12. 사용자 신고

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant User as User
    participant DB as PostgreSQL(Auth/Profile)
    participant Cache as Redis Cache(BlockList)
    participant Bus as Message Bus(Kafka/RabbitMQ/Redis)
    participant Moderation as Moderation

    Client->>APIGW: POST /api/v1/users/{target_user_id}/reports (body: { reasons, block })
    APIGW->>Auth: JWT 검증
    alt 인증 실패
        Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
    else 인증 성공
        APIGW->>User: 사용자 신고 요청
        User->>DB: INSERT INTO user_reports (reporter_id, target_user_id, reasons) VALUES (...)
        DB-->>User: 201 Created + 신고 정보
        opt block=true
            User->>Cache: SADD blocks:{reporter_id} {target_user_id}
            User->>Bus: publish UserBlocked 이벤트
        end
        User->>Bus: publish UserReported 이벤트
        Bus->>Moderation: UserReported 이벤트
        User-->>APIGW: 201 Created + { report_id }
    end
    APIGW-->>Client: 신고 결과 반환
```

#### 13. 사용자 알림 설정

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant User as User
    participant DB as PostgreSQL(Auth/Profile)
    participant Bus as Message Bus(Kafka/RabbitMQ/Redis)

    opt 알림 설정 조회
        Client->>APIGW: GET /api/v1/notifications/settings
        APIGW->>Auth: JWT 검증
        alt 인증 실패
            Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
        else 인증 성공
            APIGW->>User: 알림 설정 조회 요청
            User->>DB: SELECT follow, post, comment, like FROM notification_settings WHERE user_id = 요청자
            DB-->>User: 설정 데이터 반환
            User-->>APIGW: 200 OK + { follow, post, comment, like }
        end
    end
    opt 알림 설정 변경
        Client->>APIGW: PUT /api/v1/notifications/settings (body: { follow, post, comment, like })
        APIGW->>Auth: JWT 검증
        alt 인증 실패
            Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
        else 인증 성공
            APIGW->>User: 알림 설정 변경 요청
            User->>DB: UPDATE notification_settings SET follow = ..., post = ..., comment = ..., like = ... WHERE user_id = 요청자
            DB-->>User: 업데이트 결과 반환
            User->>Bus: publish NotificationSettingsUpdated 이벤트
            User-->>APIGW: 200 OK + { follow, post, comment, like }
        end
    end
    APIGW-->>Client: 응답 반환
```

#### 14. 사용자 검색

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant Search as Search
    participant OpenSearch as OpenSearch Cluster(Search Index)

    Client->>APIGW: GET /api/v1/search/users?q={검색어}&page={페이지}
    APIGW->>Auth: JWT 검증
    alt 인증 실패
        Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
    else 인증 성공
        APIGW->>Search: 사용자 검색 요청
        Search->>OpenSearch: 인덱스 조회 (이름·닉네임·키워드 매칭)
        OpenSearch-->>Search: 검색 결과 반환
        Search-->>APIGW: 200 OK + { results: […], total, page }
    end
    APIGW-->>Client: 검색 결과 반환
```

#### 15. 사용자 필터링

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant Post as Post
    participant Comment as Comment
    participant Cache as Redis Cache(FilterRules)
    participant Moderation as Moderation
    participant DB as PostgreSQL(Feed)
    participant Bus as Message Bus(Kafka/RabbitMQ/Redis)

    opt 게시물 작성
        Client->>APIGW: POST /api/v1/posts (body: { content, media, poll })
        APIGW->>Auth: JWT 검증
        alt 인증 실패
            Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
        else 인증 성공
            APIGW->>Post: 게시물 작성 요청
            Post->>Cache: GET filter_rules
            Cache-->>Post: 필터링 규칙 반환
            Post->>Post: 키워드·패턴 검사
            Post->>Moderation: NSFW·ML 검사 요청
            Moderation-->>Post: 검사 결과
            alt 부적절 콘텐츠 검출
                Post-->>APIGW: 400 Bad Request + { error: "Content violates policies" }
            else 콘텐츠 적합
                Post->>DB: INSERT INTO posts(...)
                DB-->>Post: 201 Created + { post_id }
                Post->>Bus: publish PostCreated 이벤트
                Post-->>APIGW: 201 Created + { post_id }
            end
        end
    end

    opt 댓글 작성
        Client->>APIGW: POST /api/v1/posts/{post_id}/comments (body: { content, media })
        APIGW->>Auth: JWT 검증
        alt 인증 실패
            Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
        else 인증 성공
            APIGW->>Comment: 댓글 작성 요청
            Comment->>Cache: GET filter_rules
            Cache-->>Comment: 필터링 규칙 반환
            Comment->>Comment: 키워드·패턴 검사
            Comment->>Moderation: NSFW·ML 검사 요청
            Moderation-->>Comment: 검사 결과
            alt 부적절 콘텐츠 검출
                Comment-->>APIGW: 400 Bad Request + { error: "Content violates policies" }
            else 콘텐츠 적합
                Comment->>DB: INSERT INTO comments(...)
                DB-->>Comment: 201 Created + { comment_id }
                Comment->>Bus: publish CommentCreated 이벤트
                Comment-->>APIGW: 201 Created + { comment_id }
            end
        end
    end
    APIGW-->>Client: 요청 결과 반환
```

### 2. 게시물 관리

#### 1. 게시물 작성

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant Post as Post
    participant Media as Media
    participant Poll as Poll
    participant DB as PostgreSQL
    participant Bus as Message Bus(Kafka/RabbitMQ/Redis)

    Client->>APIGW: POST /api/v1/posts (body: { content, images, videos, poll })
    APIGW->>Auth: JWT 검증
    alt 인증 실패
        Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
    else 인증 성공
        APIGW->>Post: 게시물 생성 요청
        opt 미디어 업로드
            Post->>Media: 이미지·동영상 저장 요청
            Media-->>Post: 미디어 URL 반환
        end
        opt 투표 생성
            Post->>Poll: 투표 생성 요청
            Poll-->>Post: 투표 ID 반환
        end
        Post->>DB: INSERT INTO posts (content, media_urls, poll_id) VALUES (...)
        DB-->>Post: 201 Created + { post_id, author_id, created_at }
        Post->>Bus: publish PostCreated 이벤트
        Post-->>APIGW: 201 Created + { post_id, author, created_at }
    end
    APIGW-->>Client: 생성 결과 반환
```

#### 2. 게시물 조회

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant Post as Post
    participant DB as PostgreSQL(Posts)
    participant Feed as Feed

    Client->>APIGW: GET /api/v1/posts?sort={latest|popular|following}&page={page}&size={size}
    APIGW->>Auth: JWT 검증
    alt 인증 실패
        Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
    else 인증 성공
        APIGW->>Post: 게시물 조회 요청
        alt 최신순
            Post->>DB: SELECT * FROM posts ORDER BY created_at DESC LIMIT {size} OFFSET {page×size}
            DB-->>Post: 게시물 목록
        else 인기순
            Post->>DB: SELECT * FROM posts ORDER BY like_count DESC LIMIT {size} OFFSET {page×size}
            DB-->>Post: 게시물 목록
        else 팔로우 피드
            Post->>Feed: 개인화된 팔로우 피드 요청
            Feed->>Cassandra: 팔로우 중인 사용자 게시물 조회
            Cassandra-->>Feed: 게시물 ID 리스트
            Feed->>Post: 게시물 상세 요청 (IDs)
            Post->>DB: SELECT * FROM posts WHERE id IN (…)
            DB-->>Post: 게시물 목록
        end
        Post-->>APIGW: 200 OK + { posts }
    end
    APIGW-->>Client: 응답 반환
```

#### 3. 게시물 수정

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant Post as Post
    participant Media as Media
    participant DB as PostgreSQL(Posts)
    participant Bus as Message Bus(Kafka/RabbitMQ/Redis)

    Client->>APIGW: PATCH /api/v1/posts/{post_id} (body: { content, images, videos })
    APIGW->>Auth: JWT 검증
    alt 인증 실패
        Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
    else 인증 성공
        APIGW->>Post: 게시물 수정 요청
        Post->>DB: SELECT author_id FROM posts WHERE id = {post_id}
        DB-->>Post: author_id 반환
        alt 작성자 일치
            opt 미디어 변경
                alt 이미지 추가
                    Post->>Media: 이미지 업로드 요청
                    Media-->>Post: image_url 반환
                end
                alt 이미지 제거
                    Post->>Media: 이미지 삭제 요청
                    Media-->>Post: 삭제 확인
                end
                alt 동영상 추가
                    Post->>Media: 동영상 업로드 요청
                    Media-->>Post: video_url 반환
                end
                alt 동영상 제거
                    Post->>Media: 동영상 삭제 요청
                    Media-->>Post: 삭제 확인
                end
            end
            Post->>DB: UPDATE posts SET content = ..., media_urls = ..., updated_at = now() WHERE id = {post_id}
            DB-->>Post: 200 OK + 수정된 게시물 정보
            Post->>Bus: publish PostUpdated 이벤트
            Post-->>APIGW: 200 OK + { post_id, content, media_urls, updated_at }
        else 작성자 불일치
            Post-->>APIGW: 403 Forbidden + { error: "수정 권한 없음" }
        end
    end
    APIGW-->>Client: 응답 반환
```

#### 4. 게시물 삭제

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant Post as Post
    participant DB as PostgreSQL(Posts)
    participant Bus as Message Bus(Kafka/RabbitMQ/Redis)
    participant Comment as Comment

    Client->>APIGW: DELETE /api/v1/posts/{post_id}
    APIGW->>Auth: JWT 검증
    alt 인증 실패
        Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
    else 인증 성공
        APIGW->>Post: 게시물 삭제 요청
        Post->>DB: SELECT author_id FROM posts WHERE id = {post_id}
        DB-->>Post: author_id 반환
        alt 작성자 일치
            Post->>DB: DELETE FROM posts WHERE id = {post_id}
            DB-->>Post: 200 OK
            Post->>Bus: publish PostDeleted 이벤트
            par 댓글 및 좋아요 삭제
                Bus->>Comment: PostDeleted 이벤트
                Comment->>DB: DELETE FROM comments WHERE post_id = {post_id}
            end
            Post-->>APIGW: 204 No Content
        else 작성자 불일치
            Post-->>APIGW: 403 Forbidden + { error: "삭제 권한 없음" }
        end
    end
    APIGW-->>Client: 요청 결과 반환
```

#### 5. 게시물 좋아요

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant Post as Post
    participant DB as PostgreSQL(Posts)
    participant Bus as Message Bus(Kafka/RabbitMQ/Redis)
    participant Notification as Notification

    Client->>APIGW: POST /api/v1/posts/{post_id}/like
    APIGW->>Auth: JWT 검증
    alt 인증 실패
        Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
    else 인증 성공
        APIGW->>Post: 좋아요 요청
        Post->>DB: SELECT COUNT(*) FROM post_likes WHERE user_id = 요청자 AND post_id = {post_id}
        DB-->>Post: 중복 여부 반환
        alt 중복 없음
            Post->>DB: INSERT INTO post_likes(user_id, post_id)
            DB-->>Post: 201 Created
            Post->>Bus: publish PostLiked 이벤트
            Bus->>Notification: PostLiked 이벤트
            Notification->>Notification: 푸시 알림 전송
            Post-->>APIGW: 204 No Content
        else 이미 좋아요 함
            Post-->>APIGW: 400 Bad Request + { error: "Already liked" }
        end
    end
    APIGW-->>Client: 요청 결과 반환
```

#### 6. 게시물 공유

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant Post as Post
    participant DB as PostgreSQL(Posts/Reposts)
    participant Bus as Message Bus(Kafka/RabbitMQ/Redis)
    participant Notification as Notification

    Client->>APIGW: POST /api/v1/posts/{post_id}/share
    APIGW->>Auth: JWT 검증
    alt 인증 실패
        Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
    else 인증 성공
        APIGW->>Post: 공유 요청
        Post->>DB: SELECT * FROM posts WHERE id = {post_id}
        DB-->>Post: 원본 게시물 데이터 반환
        Post->>DB: INSERT INTO reposts(user_id, original_post_id, created_at) VALUES (...)
        DB-->>Post: 201 Created + { share_id }
        Post->>Bus: publish PostShared 이벤트
        Bus->>Notification: PostShared 이벤트
        Notification->>Notification: 푸시 알림 전송
        Post-->>APIGW: 201 Created + { share_id, original_post_id, sharer_id, created_at }
    end
    APIGW-->>Client: 요청 결과 반환
```

#### 7. 게시물 해시태그

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant Post as Post
    participant DB as PostgreSQL(Posts)
    participant Bus as Message Bus(Kafka/RabbitMQ/Redis)
    participant Search as Search
    participant OpenSearch as OpenSearch Cluster

    Client->>APIGW: POST /api/v1/posts (body: { content })
    APIGW->>Auth: JWT 검증
    alt 인증 실패
        Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
    else 인증 성공
        APIGW->>Post: 게시물 생성 요청
        Post->>DB: INSERT INTO posts (content) VALUES (...)
        DB-->>Post: 201 Created + { post_id }
        Post->>Bus: publish PostCreated 이벤트 (post_id, content)
        opt 해시태그 추출
            Post->>Post: 텍스트에서 해시태그 추출
            Post->>Bus: publish HashtagsExtracted 이벤트 (post_id, hashtags)
        end
        Post-->>APIGW: 201 Created + { post_id }
    end
    APIGW-->>Client: 생성 결과 반환
    opt 해시태그 인덱싱
        Bus->>Search: HashtagsExtracted 이벤트 구독
        Search->>OpenSearch: 해시태그-게시물 매핑 색인
    end
```

#### 8. 게시물 북마크

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant Post as Post
    participant DB as PostgreSQL(Posts/Bookmarks)
    participant Bus as Message Bus(Kafka/RabbitMQ/Redis)

    opt 게시물 북마크 추가
        Client->>APIGW: POST /api/v1/posts/{post_id}/bookmark
        APIGW->>Auth: JWT 검증
        alt 인증 실패
            Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
        else 인증 성공
            APIGW->>Post: 북마크 요청
            Post->>DB: SELECT COUNT(*) FROM bookmarks WHERE user_id = key.sub AND post_id = {post_id}
            DB-->>Post: 중복 여부 반환
            alt 중복 없음
                Post->>DB: INSERT INTO bookmarks(user_id, post_id, created_at) VALUES(...)
                DB-->>Post: 201 Created
                Post->>Bus: publish PostBookmarked 이벤트
                Post-->>APIGW: 204 No Content
            else 이미 북마크됨
                Post-->>APIGW: 400 Bad Request + { error: "Already bookmarked" }
            end
        end
    end

    opt 북마크한 게시물 조회
        Client->>APIGW: GET /api/v1/bookmarks?page={page}&size={size}
        APIGW->>Auth: JWT 검증
        alt 인증 실패
            Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
        else 인증 성공
            APIGW->>Post: 북마크 목록 요청
            Post->>DB: SELECT post_id, created_at FROM bookmarks WHERE user_id = key.sub ORDER BY created_at DESC LIMIT {size} OFFSET {page*size}
            DB-->>Post: 북마크 목록 반환
            Post-->>APIGW: 200 OK + { bookmarks: […] }
        end
    end

    APIGW-->>Client: 요청 결과 반환
```

#### 9. 게시물 통계

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant Post as Post
    participant Redis as Redis Cache(ViewCounters)
    participant DB as PostgreSQL(Stats)

    Client->>APIGW: GET /api/v1/posts/{post_id}/stats
    APIGW->>Auth: JWT 검증
    alt 인증 실패
        Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
    else 인증 성공
        APIGW->>Post: 통계 조회 요청
        Post->>Redis: GET views:{post_id}
        Redis-->>Post: 조회수 반환
        Post->>DB: SELECT COUNT(*) FROM post_likes WHERE post_id = {post_id}
        DB-->>Post: 좋아요 수 반환
        Post->>DB: SELECT COUNT(*) FROM comments WHERE post_id = {post_id}
        DB-->>Post: 댓글 수 반환
        Post-->>APIGW: 200 OK + { views, likes, comments }
    end
    APIGW-->>Client: 통계 반환
```

#### 10. 게시물 신고

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant Post as Post
    participant DB as PostgreSQL(Posts)
    participant Cache as Redis Cache(BlockList)
    participant Bus as Message Bus(Kafka/RabbitMQ/Redis)
    participant Moderation as Moderation

    Client->>APIGW: POST /api/v1/posts/{post_id}/reports (body: { reasons, block })
    APIGW->>Auth: JWT 검증
    alt 인증 실패
        Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
    else 인증 성공
        APIGW->>Post: 게시물 신고 요청
        Post->>DB: INSERT INTO post_reports (reporter_id, post_id, reasons) VALUES (...)
        DB-->>Post: 201 Created + { report_id }
        opt block=true
            Post->>Cache: SADD blocks:{reporter_id} {author_id}
            Post->>Bus: publish UserBlocked 이벤트
        end
        Post->>Bus: publish PostReported 이벤트
        Bus->>Moderation: PostReported 이벤트
        Post-->>APIGW: 201 Created + { report_id }
    end
    APIGW-->>Client: 신고 결과 반환
```

#### 11. 게시물 필터링

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant Post as Post
    participant Cache as Redis Cache(FilterRules)
    participant Moderation as Moderation
    participant DB as PostgreSQL(Posts)
    participant Bus as Message Bus(Kafka/RabbitMQ/Redis)

    opt 게시물 작성 시 필터링
        Client->>APIGW: POST /api/v1/posts (body: { content, media, poll })
        APIGW->>Auth: JWT 검증
        alt 인증 실패
            Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
        else 인증 성공
            APIGW->>Post: 게시물 작성 요청
            Post->>Cache: GET filter_rules
            Cache-->>Post: 필터링 규칙 반환
            Post->>Post: 키워드·패턴 검사
            Post->>Moderation: NSFW·ML 검사 요청
            Moderation-->>Post: 검사 결과
            alt 부적절 콘텐츠
                Post-->>APIGW: 400 Bad Request + { error: "Content violates policies" }
            else 적합
                Post->>DB: INSERT INTO posts (...)
                DB-->>Post: post_id 반환
                Post->>Bus: publish PostCreated 이벤트
                Post-->>APIGW: 201 Created + { post_id }
            end
        end
    end
    opt 게시물 수정 시 필터링
        Client->>APIGW: PATCH /api/v1/posts/{post_id} (body: { content, media })
        APIGW->>Auth: JWT 검증
        alt 인증 실패
            Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
        else 인증 성공
            APIGW->>Post: 게시물 수정 요청
            Post->>DB: SELECT author_id FROM posts WHERE id = {post_id}
            DB-->>Post: author_id 반환
            alt 작성자 일치
                Post->>Cache: GET filter_rules
                Cache-->>Post: 필터링 규칙 반환
                Post->>Post: 키워드·패턴 검사
                Post->>Moderation: NSFW·ML 검사 요청
                Moderation-->>Post: 검사 결과
                alt 부적절 콘텐츠
                    Post-->>APIGW: 400 Bad Request + { error: "Content violates policies" }
                else 적합
                    Post->>DB: UPDATE posts SET content = ..., media_urls = ..., updated_at = now() WHERE id = {post_id}
                    DB-->>Post: 수정된 post_id 반환
                    Post->>Bus: publish PostUpdated 이벤트
                    Post-->>APIGW: 200 OK + { post_id }
                end
            else 작성자 불일치
                Post-->>APIGW: 403 Forbidden + { error: "수정 권한 없음" }
            end
        end
    end
    APIGW-->>Client: 요청 결과 반환
```

#### 12. 게시물 알림

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant Post as Post
    participant DB as PostgreSQL(Posts/Follow)
    participant Bus as Message Bus(Kafka/RabbitMQ/Redis)
    participant Notification as Notification

    Client->>APIGW: POST /api/v1/posts (body: { content, media, poll })
    APIGW->>Auth: JWT 검증
    alt 인증 실패
        Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
    else 인증 성공
        APIGW->>Post: 게시물 작성 요청
        Post->>DB: INSERT INTO posts (...)
        DB-->>Post: 201 Created + { post_id, author_id, created_at }
        Post->>Bus: publish PostCreated 이벤트
        Post-->>APIGW: 201 Created + { post_id, author_id, created_at }
    end
    APIGW-->>Client: 생성 결과 반환
    opt 새 게시물 알림 전송
        Bus->>Notification: PostCreated 이벤트
        Notification->>DB: SELECT follower_id FROM follows WHERE following_id = author_id
        DB-->>Notification: 팔로워 목록
        loop 팔로워마다
            Notification->>Notification: 푸시 알림 전송 (follower_id)
        end
    end
```

#### 13. 게시물 검색

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant Search as Search
    participant OpenSearch as OpenSearch Cluster

    Client->>APIGW: GET /api/v1/posts/search?q={query}&page={page}&size={size}
    APIGW->>Auth: JWT 검증
    alt 인증 실패
        Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
    else 인증 성공
        APIGW->>Search: 게시물 검색 요청
        Search->>OpenSearch: 인덱스 조회 (본문·해시태그 매칭)
        OpenSearch-->>Search: 검색 결과 반환
        Search-->>APIGW: 200 OK + { results, total, page }
    end
    APIGW-->>Client: 검색 결과 반환
```

### 3. 댓글 관리

#### 1. 댓글 작성

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant Comment as Comment
    participant Media as Media
    participant DB as PostgreSQL(Comments)
    participant Bus as Message Bus(Kafka/RabbitMQ/Redis)

    Client->>APIGW: POST /api/v1/posts/{post_id}/comments (body: { content, media, video })
    APIGW->>Auth: JWT 검증
    alt 인증 실패
        Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
    else 인증 성공
        APIGW->>Comment: 댓글 작성 요청
        opt 미디어 첨부
            Comment->>Media: 이미지·동영상 저장 요청
            Media-->>Comment: media_url 반환
        end
        Comment->>DB: INSERT INTO comments (post_id, user_id, content, media_urls, created_at) VALUES (...)
        DB-->>Comment: 201 Created + { comment_id, author, created_at }
        Comment->>Bus: publish CommentCreated 이벤트
        Comment-->>APIGW: 201 Created + { comment_id, author, created_at }
    end
    APIGW-->>Client: 생성 결과 반환
```

#### 2. 댓글 조회

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant Comment as Comment
    participant DB as PostgreSQL(Comments)

    Client->>APIGW: GET /api/v1/posts/{post_id}/comments?sort={latest|popular}&page={page}&size={size}
    APIGW->>Auth: JWT 검증
    alt 인증 실패
        Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
    else 인증 성공
        APIGW->>Comment: 댓글 조회 요청
        alt 최신순
            Comment->>DB: SELECT * FROM comments WHERE post_id = {post_id} ORDER BY created_at DESC LIMIT {size} OFFSET {page*size}
        else 인기순
            Comment->>DB: SELECT * FROM comments WHERE post_id = {post_id} ORDER BY like_count DESC LIMIT {size} OFFSET {page*size}
        end
        DB-->>Comment: 댓글 목록 반환
        Comment-->>APIGW: 200 OK + { comments }
    end
    APIGW-->>Client: 조회 결과 반환
```

#### 3. 댓글 수정

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant Comment as Comment
    participant Media as Media
    participant DB as PostgreSQL(Comments)
    participant Bus as Message Bus(Kafka/RabbitMQ/Redis)

    Client->>APIGW: PATCH /api/v1/posts/{post_id}/comments/{comment_id} (body: { content, media })
    APIGW->>Auth: JWT 검증
    alt 인증 실패
        Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
    else 인증 성공
        APIGW->>Comment: 댓글 수정 요청
        Comment->>DB: SELECT author_id FROM comments WHERE id = {comment_id}
        DB-->>Comment: author_id 반환
        alt 작성자 일치
            opt 미디어 변경
                alt 이미지 추가
                    Comment->>Media: 이미지 업로드 요청
                    Media-->>Comment: image_url 반환
                end
                alt 이미지 제거
                    Comment->>Media: 이미지 삭제 요청
                    Media-->>Comment: 삭제 확인
                end
                alt 동영상 추가
                    Comment->>Media: 동영상 업로드 요청
                    Media-->>Comment: video_url 반환
                end
                alt 동영상 제거
                    Comment->>Media: 동영상 삭제 요청
                    Media-->>Comment: 삭제 확인
                end
            end
            Comment->>DB: UPDATE comments SET content = ..., media_urls = ..., updated_at = now() WHERE id = {comment_id}
            DB-->>Comment: 수정된 comment_id, updated_at 반환
            Comment->>Bus: publish CommentUpdated 이벤트
            Comment-->>APIGW: 200 OK + { comment_id, content, media_urls, updated_at }
        else 작성자 불일치
            Comment-->>APIGW: 403 Forbidden + { error: "수정 권한 없음" }
        end
    end
    APIGW-->>Client: 응답 반환
```

#### 4. 댓글 삭제

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant Comment as Comment
    participant DB as PostgreSQL(Comments)
    participant Bus as Message Bus(Kafka/RabbitMQ/Redis)

    Client->>APIGW: DELETE /api/v1/posts/{post_id}/comments/{comment_id}
    APIGW->>Auth: JWT 검증
    alt 인증 실패
        Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
    else 인증 성공
        APIGW->>Comment: 댓글 삭제 요청
        Comment->>DB: SELECT author_id FROM comments WHERE id = {comment_id}
        DB-->>Comment: author_id 반환
        alt 작성자 일치
            Comment->>DB: DELETE FROM comments WHERE id = {comment_id}
            DB-->>Comment: 204 No Content
            Comment->>Bus: publish CommentDeleted 이벤트
            Comment-->>APIGW: 204 No Content
        else 작성자 불일치
            Comment-->>APIGW: 403 Forbidden + { error: "삭제 권한 없음" }
        end
    end
    APIGW-->>Client: 요청 결과 반환
```

#### 5. 대댓글

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant Comment as Comment
    participant Media as Media
    participant DB as PostgreSQL(Comments)
    participant Bus as Message Bus(Kafka/RabbitMQ/Redis)

    opt 대댓글 작성
        Client->>APIGW: POST /api/v1/posts/{post_id}/comments/{comment_id}/replies (body: { content, media })
        APIGW->>Auth: JWT 검증
        alt 인증 실패
            Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
        else 인증 성공
            APIGW->>Comment: 대댓글 작성 요청
            Comment->>DB: SELECT * FROM comments WHERE id = {comment_id}
            DB-->>Comment: 부모 댓글 존재 여부 확인
            alt 부모 댓글 존재
                opt 미디어 첨부
                    Comment->>Media: 이미지·동영상 저장 요청
                    Media-->>Comment: media_url 반환
                end
                Comment->>DB: INSERT INTO comments (post_id, parent_id, user_id, content, media_urls, created_at) VALUES (...)
                DB-->>Comment: 201 Created + { reply_id, author, created_at }
                Comment->>Bus: publish CommentReplied 이벤트
                Comment-->>APIGW: 201 Created + { reply_id, author, created_at }
            else 부모 댓글 없음
                Comment-->>APIGW: 404 Not Found + { error: "Parent Comment Not Found" }
            end
        end
    end
    opt 대댓글 조회
        Client->>APIGW: GET /api/v1/posts/{post_id}/comments/{comment_id}/replies?page={page}&size={size}
        APIGW->>Auth: JWT 검증
        alt 인증 실패
            Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
        else 인증 성공
            APIGW->>Comment: 대댓글 조회 요청
            Comment->>DB: SELECT * FROM comments WHERE parent_id = {comment_id} ORDER BY created_at DESC LIMIT {size} OFFSET {page*size}
            DB-->>Comment: 대댓글 목록 반환
            Comment-->>APIGW: 200 OK + { replies }
        end
    end
    APIGW-->>Client: 요청 결과 반환
```

#### 6. 댓글 좋아요

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant Comment as Comment
    participant DB as PostgreSQL(Comments/Likes)
    participant Bus as Message Bus(Kafka/RabbitMQ/Redis)
    participant Notification as Notification

    Client->>APIGW: POST /api/v1/comments/{comment_id}/like
    APIGW->>Auth: JWT 검증
    alt 인증 실패
        Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
    else 인증 성공
        APIGW->>Comment: 좋아요 요청
        Comment->>DB: SELECT COUNT(*) FROM comment_likes WHERE user_id = key.sub AND comment_id = {comment_id}
        DB-->>Comment: 중복 여부 반환
        alt 중복 없음
            Comment->>DB: INSERT INTO comment_likes(user_id, comment_id)
            DB-->>Comment: 201 Created
            Comment->>Bus: publish CommentLiked 이벤트
            Bus->>Notification: CommentLiked 이벤트
            Notification->>Notification: 푸시 알림 전송
            Comment-->>APIGW: 204 No Content
        else 이미 좋아요 함
            Comment-->>APIGW: 400 Bad Request + { error: "Already liked" }
        end
    end
    APIGW-->>Client: 요청 결과 반환
```

#### 7. 댓글 신고

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant Comment as Comment
    participant DB as PostgreSQL(Comments/Reports)
    participant Cache as Redis Cache(BlockList)
    participant Bus as Message Bus(Kafka/RabbitMQ/Redis)
    participant Moderation as Moderation

    Client->>APIGW: POST /api/v1/comments/{comment_id}/reports (body: { reasons, block })
    APIGW->>Auth: JWT 검증
    alt 인증 실패
        Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
    else 인증 성공
        APIGW->>Comment: 댓글 신고 요청
        Comment->>DB: INSERT INTO comment_reports (reporter_id, comment_id, reasons) VALUES (...)
        DB-->>Comment: 201 Created + 신고 정보
        opt block=true
            Comment->>Cache: SADD blocks:{reporter_id} {target_user_id}
            Comment->>Bus: publish UserBlocked 이벤트
        end
        Comment->>Bus: publish CommentReported 이벤트
        Bus->>Moderation: CommentReported 이벤트
        Comment-->>APIGW: 201 Created + { report_id }
    end
    APIGW-->>Client: 신고 결과 반환
```

#### 8. 댓글 필터링

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant Comment as Comment
    participant Cache as Redis Cache(FilterRules)
    participant Moderation as Moderation
    participant DB as PostgreSQL(Comments)

    opt 댓글 작성 시 필터링
        Client->>APIGW: POST /api/v1/posts/{post_id}/comments (body: { content, media })
        APIGW->>Auth: JWT 검증
        alt 인증 실패
            Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
        else 인증 성공
            APIGW->>Comment: 댓글 작성 요청
            Comment->>Cache: GET filter_rules
            Cache-->>Comment: 필터링 규칙 반환
            Comment->>Comment: 키워드·패턴 검사
            Comment->>Moderation: NSFW·ML 검사 요청
            Moderation-->>Comment: 검사 결과
            alt 부적절 콘텐츠
                Comment-->>APIGW: 400 Bad Request + { error: "Content violates policies" }
            else 적합
                Comment->>DB: INSERT INTO comments (post_id, user_id, content, media_urls) VALUES (...)
                DB-->>Comment: 201 Created + { comment_id, author, created_at }
                Comment->>Bus: publish CommentCreated 이벤트
                Comment-->>APIGW: 201 Created + { comment_id, author, created_at }
            end
        end
    end
    opt 댓글 수정 시 필터링
        Client->>APIGW: PATCH /api/v1/posts/{post_id}/comments/{comment_id} (body: { content, media })
        APIGW->>Auth: JWT 검증
        alt 인증 실패
            Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
        else 인증 성공
            APIGW->>Comment: 댓글 수정 요청
            Comment->>DB: SELECT author_id FROM comments WHERE id = {comment_id}
            DB-->>Comment: author_id 반환
            alt 작성자 일치
                Comment->>Cache: GET filter_rules
                Cache-->>Comment: 필터링 규칙 반환
                Comment->>Comment: 키워드·패턴 검사
                Comment->>Moderation: NSFW·ML 검사 요청
                Moderation-->>Comment: 검사 결과
                alt 부적절 콘텐츠
                    Comment-->>APIGW: 400 Bad Request + { error: "Content violates policies" }
                else 적합
                    Comment->>DB: UPDATE comments SET content = ..., media_urls = ..., updated_at = now() WHERE id = {comment_id}
                    DB-->>Comment: 200 OK + { comment_id, updated_at }
                    Comment->>Bus: publish CommentUpdated 이벤트
                    Comment-->>APIGW: 200 OK + { comment_id, updated_at }
                end
            else 작성자 불일치
                Comment-->>APIGW: 403 Forbidden + { error: "수정 권한 없음" }
            end
        end
    end
    APIGW-->>Client: 요청 결과 반환
```

#### 9. 댓글 알림

```mermaid
sequenceDiagram
    participant Client as Client
    participant APIGW as API Gateway(Nginx Ingress)
    participant Auth as Auth
    participant Comment as Comment
    participant DBComments as PostgreSQL(Comments)
    participant Bus as Message Bus(Kafka/RabbitMQ/Redis)
    participant Notification as Notification
    participant DBPosts as PostgreSQL(Posts)
    participant DBFollow as PostgreSQL(Profile)

    Client->>APIGW: POST /api/v1/posts/{post_id}/comments
    APIGW->>Auth: JWT 검증
    alt 인증 실패
        Auth-->>APIGW: 401 Unauthorized + { error: "Authentication Required" }
    else
        APIGW->>Comment: 댓글 작성 요청
        Comment->>DBComments: INSERT INTO comments (post_id, user_id, content, media_urls, created_at)
        DBComments-->>Comment: 201 Created + { comment_id, post_id, user_id, created_at }
        Comment->>Bus: publish CommentCreated 이벤트
        Comment-->>APIGW: 201 Created + { comment_id, author, created_at }
    end
    APIGW-->>Client: 생성 결과 반환
    opt 알림 전송
        Bus->>Notification: CommentCreated 이벤트
        Notification->>DBPosts: SELECT user_id FROM posts WHERE id = {post_id}
        DBPosts-->>Notification: post_author_id
        Notification->>Notification: 푸시 알림 전송 (post_author_id)
        Notification->>DBFollow: SELECT follower_id FROM follows WHERE following_id = post_author_id
        DBFollow-->>Notification: [follower_id…]
        loop for each follower_id
            Notification->>Notification: 푸시 알림 전송 (follower_id)
        end
    end
```

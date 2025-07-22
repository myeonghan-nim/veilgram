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

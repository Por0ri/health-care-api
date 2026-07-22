# HEALTH CARE REST WEB

Python CLI 프론트를 HTML/CSS/JavaScript 웹 프론트로 교체하고, Flask 백엔드를 자원 중심 REST API로 정리한 제출용 프로젝트입니다.

## 구성

```text
HEALTH-CARE-REST-WEB/
├─ back/
│  ├─ api/
│  │  ├─ auth.py
│  │  ├─ measurement_api.py
│  │  ├─ responses.py
│  │  ├─ session_api.py
│  │  ├─ system_api.py
│  │  └─ user_api.py
│  ├─ database.py
│  └─ server.py
├─ front/
│  ├─ css/styles.css
│  ├─ js/
│  │  ├─ admin.js
│  │  ├─ api.js
│  │  ├─ index.js
│  │  └─ user.js
│  ├─ admin.html
│  ├─ index.html
│  └─ user.html
├─ nginx/default.conf
├─ Dockerfile.backend
├─ Dockerfile.frontend
├─ compose.yaml
├─ requirements.txt
└─ README.md
```

## REST API

```text
POST   /api/users
GET    /api/users?keyword={검색어}
GET    /api/users/{user_id}
GET    /api/users/{user_id}/measurements

POST   /api/sessions
DELETE /api/sessions/current

GET    /api/measurements
POST   /api/measurements
GET    /api/measurements/{measurement_id}

GET    /api/health
GET    /api
```

### 회원가입

```http
POST /api/users
Content-Type: application/json
```

```json
{
  "user_id": "user01",
  "pw": "1234",
  "name": "홍길동",
  "birth": "2002-05-15"
}
```

### 로그인

사용자와 관리자 로그인은 세션 자원 생성으로 통합했습니다.

```http
POST /api/sessions
Content-Type: application/json
```

```json
{
  "role": "user",
  "account_id": "user01",
  "pw": "1234"
}
```

관리자는 `role`을 `admin`으로 보냅니다.

로그인 성공 후 보호된 API에는 다음 헤더를 전송합니다.

```http
Authorization: Bearer {token}
```

### 로그아웃

```http
DELETE /api/sessions/current
Authorization: Bearer {token}
```

## Docker 실행

프로젝트 최상위 폴더에서:

```bash
docker compose up --build -d
```

브라우저 접속:

```text
http://localhost
```

80번 포트가 이미 사용 중이면:

```bash
FRONTEND_PORT=8080 docker compose up --build -d
```

접속 주소:

```text
http://localhost:8080
```

종료:

```bash
docker compose down
```

데이터까지 삭제:

```bash
docker compose down -v
```

## Lightsail 배포 흐름

1. Lightsail 인스턴스에 Docker와 Docker Compose 설치
2. 프로젝트 업로드 또는 Git clone
3. Lightsail 네트워킹에서 TCP 80 허용
4. 프로젝트 폴더에서 `docker compose up --build -d`
5. Lightsail 고정 IP로 접속

```text
http://LIGHTSAIL_고정_IP
```

## 관리자 기본 계정

```text
ID: admin
PW: admin
```

## 인증 저장 방식

로그인 토큰은 서버 프로세스 메모리가 아니라 SQLite의 `sessions` 테이블에 저장합니다. 따라서 Gunicorn 작업 프로세스가 여러 개여도 동일한 세션을 조회할 수 있습니다.

## 측정값 검증

- 사용자별 같은 날짜는 한 번만 등록
- 바로 전날 기록이 있는 경우 키 차이 3cm 이상 차단
- 바로 전날 기록이 있는 경우 몸무게 차이 5kg 이상 차단
- 수축기 혈압은 이완기 혈압보다 커야 함
- 미래 날짜 측정값 등록 차단

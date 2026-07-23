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
PUT    /api/measurements/{measurement_id}
DELETE /api/measurements/{measurement_id}

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


## 측정 기록 삭제 권한

- 사용자는 본인의 측정 기록만 삭제할 수 있습니다.
- 관리자는 모든 사용자의 측정 기록을 삭제할 수 있습니다.
- 사용자 및 관리자 화면 모두 삭제 전 확인창을 표시합니다.
- 삭제 권한은 JavaScript 화면뿐 아니라 Flask 서버에서도 다시 검사합니다.
- 삭제된 측정 기록은 SQLite에서 영구 삭제되며 복구 기능은 포함하지 않습니다.


## BMI·혈압·공복 혈당 자동 계산

측정 기록 생성 시 Flask 서버가 입력값을 먼저 계산하고 분류한 뒤 SQLite에 저장합니다.

### BMI

```text
18.5 미만       저체중       노란색
18.5 이상 23 미만 정상        초록색
23 이상 25 미만  과체중       주황색
25 이상          비만         빨간색
```

BMI는 `몸무게(kg) ÷ 키(m)²`로 계산하며 소수점 첫째 자리로 반올림한 값을 분류합니다.

### 혈압

```text
수축기 <120 그리고 이완기 <80      정상      초록색
수축기 120~139 또는 이완기 80~89   주의      주황색
수축기 >=140 또는 이완기 >=90      고혈압    빨간색
```

### 공복 혈당

```text
100 미만       정상            초록색
100~125        공복혈당장애     주황색
126 이상       당뇨 의심       빨간색
```

### 종합 결과

- 비만, 고혈압, 당뇨 의심 중 하나라도 포함되면 전체 기록을 빨간색 위험 기록으로 표시합니다.
- 빨간색 위험 수치가 없고 주황색 항목이 있으면 종합 결과는 `주의`입니다.
- 저체중만 해당하면 종합 결과는 `관찰`입니다.
- 모든 항목이 정상이면 `정상`입니다.
- 계산할 수 없는 항목은 `해당 없음`으로 표시합니다.
- 위험 기록을 등록하면 사용자 화면에 경고 메시지가 출력됩니다.

기존 SQLite DB에 저장된 측정 기록도 서버 시작 시 새 분류 컬럼을 자동 추가하고 재계산합니다.

> 이 분류는 과제용 참고 표시이며 의료 진단을 대신하지 않습니다.


## 측정 기록 목록과 상세 표시

목록에서는 입력한 측정 수치와 계산·판정 결과를 그룹으로 분리해 표시합니다. 목록에는 상태 색상을 적용하지 않고, 상세 조회 화면에서 BMI·혈압·공복 혈당 판정에만 노랑·초록·주황·빨강·회색 상태 색상을 적용합니다.


## 측정 기록 목록 표시 방식

목록에는 다음 항목만 표시합니다.

```text
날짜
키
몸무게
BMI 판정
공복 혈당 판정
혈압 판정
관리
```

BMI 숫자, 공복 혈당 숫자, 수축기·이완기 혈압 숫자는 `상세` 화면에서만 표시합니다. 목록에는 `정상`, `저체중`, `과체중`, `비만`, `주의`, `고혈압`, `공복혈당장애`, `당뇨 의심`, `해당 없음`과 같은 판정 결과만 표시합니다.

판정 색상 역시 목록에는 사용하지 않고 상세 화면의 결과 카드에만 적용합니다.

측정 입력 폼은 작은 화면에서도 날짜와 숫자 입력 셀이 겹치지 않도록 각 입력 요소에 최소 너비와 반응형 간격을 적용했습니다.


## 측정 기록 전체 수정(PUT)

사용자는 본인의 측정 기록만 전체 수정할 수 있습니다.

```http
PUT /api/measurements/{measurement_id}
Authorization: Bearer {사용자 토큰}
Content-Type: application/json
```

```json
{
  "date": "2026-07-21",
  "height": 178.9,
  "weight": 63.5,
  "systolic": 118,
  "diastolic": 78,
  "blood_sugar": 92,
  "memo": "재측정값으로 전체 수정"
}
```

PUT 요청은 날짜·키·몸무게·수축기 혈압·이완기 혈압·공복 혈당을 모두 요구합니다. 서버는 다음 처리를 다시 수행합니다.

- 같은 날짜의 다른 기록 중복 검사
- 수정된 날짜의 전날과 다음 날 키·몸무게 차이 검사
- BMI 재계산 및 재분류
- 혈압과 공복 혈당 재분류
- 종합 결과와 경고 메시지 갱신

관리자는 측정 기록을 조회·삭제할 수 있지만 PUT 수정은 할 수 없습니다.

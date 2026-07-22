# REST API 명세

기본 URL은 Nginx를 기준으로 `/api`입니다.

## 공통 응답 형식

성공:

```json
{
  "success": true,
  "message": "처리 결과",
  "data": {}
}
```

실패:

```json
{
  "success": false,
  "message": "오류 설명",
  "error_type": "validation"
}
```

## 사용자

### POST /api/users

새 사용자를 생성합니다.

성공 상태: `201 Created`

## 세션

### POST /api/sessions

사용자 또는 관리자 로그인 세션을 생성합니다.

성공 상태: `201 Created`

### DELETE /api/sessions/current

현재 로그인 세션을 삭제합니다.

성공 상태: `200 OK`

## 측정 정보

### GET /api/measurements

현재 로그인한 사용자의 측정 정보 목록을 조회합니다.

권한: 사용자

### POST /api/measurements

현재 로그인한 사용자의 측정 정보를 생성합니다.

권한: 사용자  
성공 상태: `201 Created`

### GET /api/measurements/{measurement_id}

측정 정보 하나를 조회합니다.

권한:
- 사용자는 본인 정보만 조회
- 관리자는 모든 사용자의 정보 조회

## 관리자 사용자 조회

### GET /api/users

사용자 목록을 조회합니다.

권한: 관리자

선택 쿼리:

```text
?keyword=홍길동
```

### GET /api/users/{user_id}

사용자 한 명을 조회합니다.

권한: 관리자

### GET /api/users/{user_id}/measurements

특정 사용자의 측정 목록을 조회합니다.

권한: 관리자


### DELETE /api/measurements/{measurement_id}

측정 기록 하나를 영구 삭제합니다.

권한:

- 사용자는 본인의 측정 기록만 삭제할 수 있습니다.
- 관리자는 모든 사용자의 측정 기록을 삭제할 수 있습니다.
- 다른 사용자의 기록을 삭제하려는 일반 사용자 요청은 `403 Forbidden`으로 거부됩니다.

성공 상태: `200 OK`

성공 응답 예시:

```json
{
  "success": true,
  "message": "측정 기록이 삭제되었습니다.",
  "data": {
    "measurement_id": 1,
    "user_id": "user01",
    "deleted_by": {
      "role": "admin",
      "account_id": "admin"
    }
  }
}
```

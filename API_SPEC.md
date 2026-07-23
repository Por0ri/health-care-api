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



### PUT /api/measurements/{measurement_id}

사용자가 본인의 측정 기록 전체를 교체합니다.

권한: 사용자 본인만 가능  
성공 상태: `200 OK`

요청 본문에는 다음 필드를 모두 포함해야 합니다.

```json
{
  "date": "2026-07-21",
  "height": 178.9,
  "weight": 63.5,
  "systolic": 118,
  "diastolic": 78,
  "blood_sugar": 92,
  "memo": "재측정값으로 수정"
}
```

처리 순서:

1. 측정 기록 존재 여부 및 소유권 검사
2. 전체 입력값 검증
3. 동일 날짜의 다른 기록 중복 검사
4. 전날 및 다음 날 키·몸무게 변화량 검사
5. BMI·혈압·공복 혈당 및 종합 상태 재계산
6. 기존 SQLite 행 전체 갱신
7. 수정된 측정 기록과 경고 배열 반환

관리자 토큰으로 요청하면 `403 Forbidden`을 반환합니다.

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


## 건강 수치 계산 결과

측정 정보 응답에는 다음 계산 필드가 포함됩니다.

```json
{
  "bmi": 31.1,
  "bmi_category": "비만",
  "bmi_status": "red",
  "blood_pressure_category": "고혈압",
  "blood_pressure_status": "red",
  "fasting_glucose_category": "당뇨 의심",
  "fasting_glucose_status": "red",
  "overall_category": "위험",
  "overall_status": "red",
  "warning_message": "BMI가 비만 범위입니다.\n혈압이 고혈압 범위입니다.\n공복 혈당이 당뇨 의심 범위입니다.",
  "warnings": [
    "BMI가 비만 범위입니다.",
    "혈압이 고혈압 범위입니다.",
    "공복 혈당이 당뇨 의심 범위입니다."
  ]
}
```

상태 색상 키:

```text
yellow  노란색
green   초록색
orange  주황색
red     빨간색
neutral 해당 없음
```

### POST /api/measurements 처리 순서

1. 입력값 검증
2. 전날 키·몸무게 변화량 검증
3. BMI·혈압·공복 혈당 계산 및 분류
4. 계산 결과와 원본 측정값을 함께 SQLite에 저장
5. 위험 항목이 있으면 `warnings` 배열로 반환

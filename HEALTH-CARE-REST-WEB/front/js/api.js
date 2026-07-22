const API_BASE_URL = "/api";
const SESSION_STORAGE_KEY = "healthCareSession";

class ApiError extends Error {
  constructor(message, status, errorType) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.errorType = errorType;
  }
}

async function apiRequest(path, options = {}) {
  const session = getStoredSession();
  const headers = new Headers(options.headers || {});

  headers.set("Accept", "application/json");

  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (session?.token) {
    headers.set("Authorization", `Bearer ${session.token}`);
  }

  let response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers
    });
  } catch (error) {
    throw new ApiError("API 서버에 연결할 수 없습니다.", 0, "network");
  }

  let payload;

  try {
    payload = await response.json();
  } catch (error) {
    throw new ApiError(
      `서버가 JSON이 아닌 응답을 반환했습니다. HTTP ${response.status}`,
      response.status,
      "response"
    );
  }

  if (!response.ok || !payload.success) {
    if (response.status === 401) {
      clearStoredSession();
    }

    throw new ApiError(
      payload.message || "요청 처리에 실패했습니다.",
      response.status,
      payload.error_type || "api"
    );
  }

  return payload;
}

function storeSession(session) {
  localStorage.setItem(
    SESSION_STORAGE_KEY,
    JSON.stringify(session)
  );
}

function getStoredSession() {
  const rawValue = localStorage.getItem(SESSION_STORAGE_KEY);

  if (!rawValue) {
    return null;
  }

  try {
    return JSON.parse(rawValue);
  } catch (error) {
    clearStoredSession();
    return null;
  }
}

function clearStoredSession() {
  localStorage.removeItem(SESSION_STORAGE_KEY);
}

function requireSession(expectedRole) {
  const session = getStoredSession();

  if (!session || session.role !== expectedRole) {
    window.location.replace("/");
    return null;
  }

  return session;
}

async function logout() {
  try {
    await apiRequest("/sessions/current", {
      method: "DELETE"
    });
  } catch (error) {
    // 서버 세션이 이미 만료되어도 브라우저 세션은 제거한다.
  } finally {
    clearStoredSession();
    window.location.replace("/");
  }
}

function showMessage(element, message, type = "error") {
  element.textContent = message;
  element.className = `message ${type}`;
}

function hideMessage(element) {
  element.textContent = "";
  element.className = "message hidden";
}

function formatMeasurementDetail(measurement) {
  const entries = [
    ["측정 ID", measurement.id],
    ["사용자 ID", measurement.user_id],
    ["측정 날짜", measurement.date],
    ["키", `${Number(measurement.height).toFixed(1)} cm`],
    ["몸무게", `${Number(measurement.weight).toFixed(1)} kg`],
    ["수축기 혈압", measurement.systolic],
    ["이완기 혈압", measurement.diastolic],
    ["혈당", Number(measurement.blood_sugar).toFixed(1)],
    ["메모", measurement.memo || "-"]
  ];

  return entries
    .map(([term, value]) => `<div><dt>${term}</dt><dd>${escapeHtml(value)}</dd></div>`)
    .join("");
}

function escapeHtml(value) {
  const text = String(value);
  const element = document.createElement("div");
  element.textContent = text;
  return element.innerHTML;
}

const API_BASE_URL = "/api";
const SESSION_STORAGE_KEY = "healthCareSession";
const VALID_STATUS_NAMES = new Set([
  "yellow",
  "green",
  "orange",
  "red",
  "neutral"
]);

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

function normalizeStatus(status) {
  return VALID_STATUS_NAMES.has(status)
    ? status
    : "neutral";
}

function renderStatusBadge(category, status) {
  const safeCategory = escapeHtml(category || "해당 없음");
  const safeStatus = normalizeStatus(status);

  return (
    `<span class="status-badge status-${safeStatus}">` +
    `${safeCategory}</span>`
  );
}

function renderMeasurementValue(value, suffix = "", digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "해당 없음";
  }

  return `${Number(value).toFixed(digits)}${suffix}`;
}

function getMeasurementRowClass(measurement) {
  const status = normalizeStatus(measurement.overall_status);

  if (status === "red") {
    return "measurement-row risk-row";
  }

  return `measurement-row measurement-row-${status}`;
}

function renderDetailStatusCard(label, value, category, status) {
  const safeStatus = normalizeStatus(status);
  return `
    <section class="detail-status-card detail-status-${safeStatus}">
      <span class="detail-status-label">${escapeHtml(label)}</span>
      <strong class="detail-status-value">${escapeHtml(value ?? "해당 없음")}</strong>
      <span class="detail-status-category">${escapeHtml(category || "해당 없음")}</span>
    </section>
  `;
}

function formatMeasurementDetail(measurement) {
  const pressureValue = (
    measurement.systolic !== null && measurement.systolic !== undefined &&
    measurement.diastolic !== null && measurement.diastolic !== undefined
  ) ? `${measurement.systolic}/${measurement.diastolic} mmHg` : "해당 없음";

  const inputEntries = [
    ["측정 날짜", measurement.date],
    ["키", renderMeasurementValue(measurement.height, " cm", 1)],
    ["몸무게", renderMeasurementValue(measurement.weight, " kg", 1)],
    ["수축기 혈압", measurement.systolic ?? "해당 없음"],
    ["이완기 혈압", measurement.diastolic ?? "해당 없음"],
    ["공복 혈당 입력값", renderMeasurementValue(measurement.blood_sugar, " mg/dL", 1)],
    ["메모", measurement.memo || "-"]
  ];

  const inputHtml = inputEntries.map(([term,value]) =>
    `<div><dt>${escapeHtml(term)}</dt><dd>${escapeHtml(value)}</dd></div>`
  ).join("");

  const warnings = measurement.warnings?.length
    ? `<div class="detail-warning-box"><strong>경고</strong><p>${measurement.warnings.map(escapeHtml).join("<br>")}</p><small>분류 결과는 참고용이며 의료 진단을 대신하지 않습니다.</small></div>`
    : `<div class="detail-no-warning"><strong>경고</strong><span>해당 없음</span></div>`;

  return `
    <div class="detail-section">
      <h3>입력한 측정 수치</h3>
      <dl class="detail-input-list">${inputHtml}</dl>
    </div>
    <div class="detail-section">
      <h3>계산 및 판정 결과</h3>
      <div class="detail-status-grid">
        ${renderDetailStatusCard("BMI", renderMeasurementValue(measurement.bmi, "", 1), measurement.bmi_category, measurement.bmi_status)}
        ${renderDetailStatusCard("혈압", pressureValue, measurement.blood_pressure_category, measurement.blood_pressure_status)}
        ${renderDetailStatusCard("공복 혈당", renderMeasurementValue(measurement.blood_sugar, " mg/dL", 1), measurement.fasting_glucose_category, measurement.fasting_glucose_status)}
      </div>
    </div>
    <div class="detail-overall detail-overall-${normalizeStatus(measurement.overall_status)}">
      <span>종합 결과</span><strong>${escapeHtml(measurement.overall_category || "해당 없음")}</strong>
    </div>
    ${warnings}
  `;
}

function escapeHtml(value) {
  const text = String(value);
  const element = document.createElement("div");
  element.textContent = text;
  return element.innerHTML;
}

document.addEventListener("DOMContentLoaded", () => {
  const session = requireSession("admin");

  if (!session) {
    return;
  }

  const PAGE_SIZE = 5;

  const state = {
    selectedUser: null,
    currentPage: 1,
    activeView: "history",
    startDate: "",
    endDate: ""
  };

  const accountLabel = document.querySelector("#account-label");
  const messageElement = document.querySelector("#message");
  const searchForm = document.querySelector("#search-form");
  const searchInput = document.querySelector("#search-input");
  const userTableBody = document.querySelector("#user-table-body");
  const userEmptyMessage = document.querySelector("#user-empty-message");

  const measurementPanel = document.querySelector("#measurement-panel");
  const selectedUserTitle = document.querySelector("#selected-user-title");
  const measurementTableBody = document.querySelector(
    "#measurement-table-body"
  );
  const measurementEmptyMessage = document.querySelector(
    "#measurement-empty-message"
  );
  const paginationElement = document.querySelector("#admin-pagination");

  const historyView = document.querySelector("#admin-history-view");
  const averageView = document.querySelector("#admin-average-view");
  const historyViewButton = document.querySelector(
    "#admin-history-view-button"
  );
  const averageViewButton = document.querySelector(
    "#admin-average-view-button"
  );

  const dateFilterForm = document.querySelector("#admin-date-filter-form");
  const startDateInput = document.querySelector(
    "#admin-filter-start-date"
  );
  const endDateInput = document.querySelector(
    "#admin-filter-end-date"
  );

  const averageCards = document.querySelector("#admin-average-cards");
  const averageEmptyMessage = document.querySelector(
    "#admin-average-empty-message"
  );
  const averagePeriodLabel = document.querySelector(
    "#admin-average-period-label"
  );

  const detailDialog = document.querySelector("#detail-dialog");
  const detailList = document.querySelector("#measurement-detail");

  accountLabel.textContent = `${session.account_id} 관리자`;

  const today = new Date().toISOString().slice(0, 10);
  startDateInput.max = today;
  endDateInput.max = today;

  document
    .querySelector("#logout-button")
    .addEventListener("click", logout);

  document
    .querySelector("#dialog-close-button")
    .addEventListener("click", () => detailDialog.close());

  document
    .querySelector("#reset-button")
    .addEventListener("click", () => {
      searchInput.value = "";
      loadUsers("");
    });

  searchForm.addEventListener("submit", (event) => {
    event.preventDefault();
    loadUsers(searchInput.value.trim());
  });

  historyViewButton.addEventListener("click", () => {
    switchView("history");
  });

  averageViewButton.addEventListener("click", () => {
    switchView("average");
  });

  dateFilterForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!applyDateFilter()) {
      return;
    }

    state.currentPage = 1;
    await refreshSelectedUserViews();
  });

  document
    .querySelector("#admin-filter-reset-button")
    .addEventListener("click", async () => {
      startDateInput.value = "";
      endDateInput.value = "";
      state.startDate = "";
      state.endDate = "";
      state.currentPage = 1;
      await refreshSelectedUserViews();
    });

  async function loadUsers(keyword = "") {
    hideMessage(messageElement);

    try {
      const query = keyword
        ? `?keyword=${encodeURIComponent(keyword)}`
        : "";
      const result = await apiRequest(`/users${query}`);
      const users = result.data.users;

      userTableBody.innerHTML = "";
      userEmptyMessage.classList.toggle("hidden", users.length > 0);

      users.forEach((user) => {
        const row = document.createElement("tr");

        row.innerHTML = `
          <td>${escapeHtml(user.user_id)}</td>
          <td>${escapeHtml(user.name)}</td>
          <td>${escapeHtml(user.birth)}</td>
          <td>${escapeHtml(user.measurement_count)}</td>
          <td>
            ${Number(user.risk_count || 0) > 0
              ? `위험 ${escapeHtml(user.risk_count)}건`
              : "해당 없음"}
          </td>
          <td>
            <button class="table-button" type="button">
              측정 기록
            </button>
          </td>
        `;

        row
          .querySelector("button")
          .addEventListener(
            "click",
            () => selectUser(user)
          );

        userTableBody.appendChild(row);
      });
    } catch (error) {
      handleApiError(error);
    }
  }

  async function selectUser(user) {
    state.selectedUser = user;
    state.currentPage = 1;
    state.startDate = "";
    state.endDate = "";
    startDateInput.value = "";
    endDateInput.value = "";

    selectedUserTitle.textContent =
      `${user.name}(${user.user_id}) 측정 기록`;
    measurementPanel.classList.remove("hidden");

    await refreshSelectedUserViews();

    measurementPanel.scrollIntoView({
      behavior: "smooth",
      block: "start"
    });
  }

  function applyDateFilter() {
    const startDate = startDateInput.value;
    const endDate = endDateInput.value;

    if (startDate && endDate && startDate > endDate) {
      showMessage(
        messageElement,
        "조회 시작일은 종료일보다 늦을 수 없습니다."
      );
      return false;
    }

    state.startDate = startDate;
    state.endDate = endDate;
    hideMessage(messageElement);
    return true;
  }

  function buildQuery(includePagination = false) {
    const parameters = new URLSearchParams();

    if (state.startDate) {
      parameters.set("start_date", state.startDate);
    }

    if (state.endDate) {
      parameters.set("end_date", state.endDate);
    }

    if (includePagination) {
      parameters.set("page", String(state.currentPage));
      parameters.set("page_size", String(PAGE_SIZE));
    }

    const query = parameters.toString();
    return query ? `?${query}` : "";
  }

  function switchView(viewName) {
    state.activeView = viewName;
    const showHistory = viewName === "history";

    historyView.classList.toggle("hidden", !showHistory);
    averageView.classList.toggle("hidden", showHistory);
    historyViewButton.classList.toggle("active", showHistory);
    averageViewButton.classList.toggle("active", !showHistory);

    if (!state.selectedUser) {
      return;
    }

    if (showHistory) {
      loadUserMeasurements();
    } else {
      loadUserStatistics();
    }
  }

  async function refreshSelectedUserViews() {
    if (!state.selectedUser) {
      return;
    }

    await Promise.all([
      loadUserMeasurements(),
      loadUserStatistics()
    ]);
  }

  async function loadUserMeasurements() {
    if (!state.selectedUser) {
      return;
    }

    try {
      const userId = encodeURIComponent(
        state.selectedUser.user_id
      );
      const result = await apiRequest(
        `/users/${userId}/measurements${buildQuery(true)}`
      );
      const measurements = result.data.measurements;
      const pagination = result.data.pagination;

      state.currentPage = pagination.page || 1;
      renderMeasurementRows(measurements);
      renderPagination(pagination);
    } catch (error) {
      handleApiError(error);
    }
  }

  function renderMeasurementRows(measurements) {
    measurementTableBody.innerHTML = "";
    measurementEmptyMessage.classList.toggle(
      "hidden",
      measurements.length > 0
    );

    measurements.forEach((measurement) => {
      const row = document.createElement("tr");
      row.className = "measurement-row";

      row.innerHTML = `
        <td>
          <button class="date-detail-button" type="button">
            ${escapeHtml(measurement.date)}
          </button>
        </td>
        <td>${renderMeasurementValue(measurement.height, " cm", 1)}</td>
        <td>${renderMeasurementValue(measurement.weight, " kg", 1)}</td>
        <td>${escapeHtml(
          measurement.bmi_category || "해당 없음"
        )}</td>
        <td>${escapeHtml(
          measurement.fasting_glucose_category || "해당 없음"
        )}</td>
        <td>${escapeHtml(
          measurement.blood_pressure_category || "해당 없음"
        )}</td>
        <td>
          <div class="action-buttons">
            <button class="table-button detail-button" type="button">
              상세
            </button>
            <button class="danger-button delete-button" type="button">
              삭제
            </button>
          </div>
        </td>
      `;

      row
        .querySelector(".date-detail-button")
        .addEventListener(
          "click",
          () => showDetail(measurement.id)
        );

      row
        .querySelector(".detail-button")
        .addEventListener(
          "click",
          () => showDetail(measurement.id)
        );

      row
        .querySelector(".delete-button")
        .addEventListener(
          "click",
          () => deleteMeasurement(
            measurement.id,
            measurement.date
          )
        );

      measurementTableBody.appendChild(row);
    });
  }

  function renderPagination(pagination) {
    paginationElement.innerHTML = "";

    if (!pagination || pagination.total_pages <= 1) {
      paginationElement.classList.add("hidden");
      return;
    }

    paginationElement.classList.remove("hidden");

    paginationElement.appendChild(
      createPageButton(
        "이전",
        pagination.page - 1,
        !pagination.has_previous
      )
    );

    for (
      let pageNumber = 1;
      pageNumber <= pagination.total_pages;
      pageNumber += 1
    ) {
      const button = createPageButton(
        String(pageNumber),
        pageNumber,
        false
      );

      if (pageNumber === pagination.page) {
        button.classList.add("active");
      }

      paginationElement.appendChild(button);
    }

    paginationElement.appendChild(
      createPageButton(
        "다음",
        pagination.page + 1,
        !pagination.has_next
      )
    );
  }

  function createPageButton(label, pageNumber, disabled) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "pagination-button";
    button.textContent = label;
    button.disabled = disabled;

    button.addEventListener("click", async () => {
      state.currentPage = pageNumber;
      await loadUserMeasurements();
    });

    return button;
  }

  async function loadUserStatistics() {
    if (!state.selectedUser) {
      return;
    }

    try {
      const userId = encodeURIComponent(
        state.selectedUser.user_id
      );
      const result = await apiRequest(
        `/users/${userId}/measurements/stats${buildQuery(false)}`
      );

      renderStatistics(result.data.statistics);
    } catch (error) {
      handleApiError(error);
    }
  }

  function renderStatistics(statistics) {
    const count = statistics.measurement_count;
    const averages = statistics.averages;

    averageCards.innerHTML = "";
    averageEmptyMessage.classList.toggle("hidden", count > 0);

    const periodStart = statistics.filters.start_date
      || statistics.first_date;
    const periodEnd = statistics.filters.end_date
      || statistics.last_date;

    averagePeriodLabel.textContent = count > 0
      ? `${periodStart} ~ ${periodEnd} · ${count}건`
      : "선택 기간 기록 없음";

    if (count === 0) {
      return;
    }

    const cards = [
      ["평균 키", averages.height, "cm"],
      ["평균 몸무게", averages.weight, "kg"],
      ["평균 BMI", averages.bmi, ""],
      ["평균 수축기 혈압", averages.systolic, "mmHg"],
      ["평균 이완기 혈압", averages.diastolic, "mmHg"],
      ["평균 공복 혈당", averages.blood_sugar, "mg/dL"]
    ];

    cards.forEach(([label, value, unit]) => {
      const card = document.createElement("article");
      card.className = "average-card";
      card.innerHTML = `
        <span>${escapeHtml(label)}</span>
        <strong>${renderMeasurementValue(value, "", 1)}</strong>
        <small>${escapeHtml(unit || "평균값")}</small>
      `;
      averageCards.appendChild(card);
    });
  }

  async function deleteMeasurement(
    measurementId,
    measurementDate
  ) {
    if (!state.selectedUser) {
      return;
    }

    const user = state.selectedUser;
    const confirmed = window.confirm(
      `${user.name}(${user.user_id}) 사용자의 ` +
      `${measurementDate} 측정 기록을 삭제할까요?\n` +
      "관리자 삭제 후에는 복구할 수 없습니다."
    );

    if (!confirmed) {
      return;
    }

    hideMessage(messageElement);

    try {
      const result = await apiRequest(
        `/measurements/${measurementId}`,
        {
          method: "DELETE"
        }
      );

      showMessage(messageElement, result.message, "success");
      await refreshSelectedUserViews();
      await loadUsers(searchInput.value.trim());
    } catch (error) {
      handleApiError(error);
    }
  }

  async function showDetail(measurementId) {
    try {
      const result = await apiRequest(`/measurements/${measurementId}`);
      detailList.innerHTML = formatMeasurementDetail(
        result.data.measurement
      );
      detailDialog.showModal();
    } catch (error) {
      handleApiError(error);
    }
  }

  function handleApiError(error) {
    if (error.status === 401 || error.status === 403) {
      window.location.replace("/");
      return;
    }

    showMessage(messageElement, error.message);
  }

  loadUsers();
});

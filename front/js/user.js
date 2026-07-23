document.addEventListener("DOMContentLoaded", () => {
  const session = requireSession("user");

  if (!session) {
    return;
  }

  const PAGE_SIZE = 5;

  const state = {
    currentPage: 1,
    activeView: "history",
    startDate: "",
    endDate: ""
  };

  const accountLabel = document.querySelector("#account-label");
  const messageElement = document.querySelector("#message");
  const form = document.querySelector("#measurement-form");
  const tableBody = document.querySelector("#measurement-table-body");
  const emptyMessage = document.querySelector("#empty-message");
  const paginationElement = document.querySelector("#pagination");

  const historyView = document.querySelector("#history-view");
  const averageView = document.querySelector("#average-view");
  const historyViewButton = document.querySelector("#history-view-button");
  const averageViewButton = document.querySelector("#average-view-button");
  const dateFilterForm = document.querySelector("#date-filter-form");
  const startDateInput = document.querySelector("#filter-start-date");
  const endDateInput = document.querySelector("#filter-end-date");
  const averageCards = document.querySelector("#average-cards");
  const averageEmptyMessage = document.querySelector(
    "#average-empty-message"
  );
  const averagePeriodLabel = document.querySelector(
    "#average-period-label"
  );

  const detailDialog = document.querySelector("#detail-dialog");
  const detailList = document.querySelector("#measurement-detail");
  const dateInput = document.querySelector("#measurement-date");

  const editDialog = document.querySelector("#edit-dialog");
  const editForm = document.querySelector("#edit-measurement-form");
  const editDateInput = document.querySelector("#edit-date");

  accountLabel.textContent = `${session.account_id} 님`;

  const today = new Date().toISOString().slice(0, 10);
  dateInput.max = today;
  dateInput.value = today;
  editDateInput.max = today;
  startDateInput.max = today;
  endDateInput.max = today;

  document
    .querySelector("#logout-button")
    .addEventListener("click", logout);

  document
    .querySelector("#refresh-button")
    .addEventListener("click", refreshViews);

  document
    .querySelector("#dialog-close-button")
    .addEventListener("click", () => detailDialog.close());

  document
    .querySelector("#edit-dialog-close-button")
    .addEventListener("click", () => editDialog.close());

  document
    .querySelector("#edit-cancel-button")
    .addEventListener("click", () => editDialog.close());

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
    await refreshViews();
  });

  document
    .querySelector("#filter-reset-button")
    .addEventListener("click", async () => {
      startDateInput.value = "";
      endDateInput.value = "";
      state.startDate = "";
      state.endDate = "";
      state.currentPage = 1;
      await refreshViews();
    });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    hideMessage(messageElement);

    const formData = new FormData(form);

    try {
      const result = await apiRequest("/measurements", {
        method: "POST",
        body: JSON.stringify({
          date: formData.get("date"),
          height: Number(formData.get("height")),
          weight: Number(formData.get("weight")),
          systolic: Number(formData.get("systolic")),
          diastolic: Number(formData.get("diastolic")),
          blood_sugar: Number(formData.get("blood_sugar")),
          memo: formData.get("memo")
        })
      });

      showMeasurementResultMessage(result);
      form.reset();
      dateInput.value = today;
      state.currentPage = 1;
      await refreshViews();
    } catch (error) {
      handleApiError(error);
    }
  });

  editForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    hideMessage(messageElement);

    const formData = new FormData(editForm);
    const measurementId = formData.get("measurement_id");

    try {
      const result = await apiRequest(
        `/measurements/${measurementId}`,
        {
          method: "PUT",
          body: JSON.stringify({
            date: formData.get("date"),
            height: Number(formData.get("height")),
            weight: Number(formData.get("weight")),
            systolic: Number(formData.get("systolic")),
            diastolic: Number(formData.get("diastolic")),
            blood_sugar: Number(formData.get("blood_sugar")),
            memo: formData.get("memo")
          })
        }
      );

      editDialog.close();
      showMeasurementResultMessage(result);
      state.currentPage = 1;
      await refreshViews();
    } catch (error) {
      handleApiError(error);
    }
  });

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

    if (showHistory) {
      loadMeasurements();
    } else {
      loadStatistics();
    }
  }

  async function refreshViews() {
    await Promise.all([
      loadMeasurements(),
      loadStatistics()
    ]);
  }

  async function loadMeasurements() {
    try {
      const result = await apiRequest(
        `/measurements${buildQuery(true)}`
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
    tableBody.innerHTML = "";
    emptyMessage.classList.toggle("hidden", measurements.length > 0);

    measurements.forEach((measurement) => {
      const row = document.createElement("tr");
      row.className = "measurement-row";
      row.innerHTML = `
        <td>
          <button
            class="date-detail-button"
            type="button"
          >
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
            <button class="edit-button update-button" type="button">
              수정
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
        .querySelector(".update-button")
        .addEventListener(
          "click",
          () => openEditDialog(measurement.id)
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

      tableBody.appendChild(row);
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
        button.setAttribute("aria-current", "page");
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
      await loadMeasurements();
    });

    return button;
  }

  async function loadStatistics() {
    try {
      const result = await apiRequest(
        `/measurements/stats${buildQuery(false)}`
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

  async function openEditDialog(measurementId) {
    hideMessage(messageElement);

    try {
      const result = await apiRequest(`/measurements/${measurementId}`);
      const measurement = result.data.measurement;

      document.querySelector("#edit-measurement-id").value =
        measurement.id;
      document.querySelector("#edit-date").value =
        measurement.date;
      document.querySelector("#edit-height").value =
        measurement.height;
      document.querySelector("#edit-weight").value =
        measurement.weight;
      document.querySelector("#edit-systolic").value =
        measurement.systolic;
      document.querySelector("#edit-diastolic").value =
        measurement.diastolic;
      document.querySelector("#edit-blood-sugar").value =
        measurement.blood_sugar;
      document.querySelector("#edit-memo").value =
        measurement.memo || "";

      editDialog.showModal();
    } catch (error) {
      handleApiError(error);
    }
  }

  async function deleteMeasurement(measurementId, measurementDate) {
    const confirmed = window.confirm(
      `${measurementDate} 측정 기록을 삭제할까요?\n` +
      "삭제된 기록은 복구할 수 없습니다."
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
      await refreshViews();
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

  function showMeasurementResultMessage(result) {
    const measurement = result.data.measurement;
    const warnings = result.data.warnings || [];

    if (measurement.overall_status === "red" || warnings.length > 0) {
      showMessage(
        messageElement,
        `${result.message} 경고: ${warnings.join(" ")} ` +
        "분류 결과는 참고용이며 의료 진단을 대신하지 않습니다.",
        "warning"
      );
    } else {
      showMessage(
        messageElement,
        `${result.message} 종합 결과: ` +
        `${measurement.overall_category}`,
        "success"
      );
    }
  }

  function handleApiError(error) {
    if (error.status === 401) {
      window.location.replace("/");
      return;
    }

    showMessage(messageElement, error.message);
  }

  refreshViews();
});

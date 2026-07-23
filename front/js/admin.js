document.addEventListener("DOMContentLoaded", () => {
  const session = requireSession("admin");

  if (!session) {
    return;
  }

  const accountLabel = document.querySelector("#account-label");
  const messageElement = document.querySelector("#message");
  const searchForm = document.querySelector("#search-form");
  const searchInput = document.querySelector("#search-input");
  const userTableBody = document.querySelector("#user-table-body");
  const userEmptyMessage = document.querySelector("#user-empty-message");
  const measurementPanel = document.querySelector("#measurement-panel");
  const selectedUserTitle = document.querySelector("#selected-user-title");
  const measurementTableBody = document.querySelector("#measurement-table-body");
  const measurementEmptyMessage = document.querySelector("#measurement-empty-message");
  const detailDialog = document.querySelector("#detail-dialog");
  const detailList = document.querySelector("#measurement-detail");

  accountLabel.textContent = `${session.account_id} 관리자`;

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
              ? renderStatusBadge(
                `위험 ${user.risk_count}건`,
                "red"
              )
              : renderStatusBadge("해당 없음", "neutral")}
          </td>
          <td><button class="table-button" type="button">측정 기록</button></td>
        `;

        row
          .querySelector("button")
          .addEventListener(
            "click",
            () => loadUserMeasurements(user)
          );

        userTableBody.appendChild(row);
      });
    } catch (error) {
      if (error.status === 401 || error.status === 403) {
        window.location.replace("/");
        return;
      }

      showMessage(messageElement, error.message);
    }
  }

  async function loadUserMeasurements(user) {
    hideMessage(messageElement);

    try {
      const result = await apiRequest(
        `/users/${encodeURIComponent(user.user_id)}/measurements`
      );
      const measurements = result.data.measurements;

      selectedUserTitle.textContent =
        `${user.name}(${user.user_id}) 측정 기록`;
      measurementTableBody.innerHTML = "";
      measurementPanel.classList.remove("hidden");
      measurementEmptyMessage.classList.toggle(
        "hidden",
        measurements.length > 0
      );

      measurements.forEach((measurement) => {
        const row = document.createElement("tr");
        row.className = getMeasurementRowClass(measurement);

        row.innerHTML = `
          <td>${escapeHtml(measurement.date)}</td>
          <td>
            <div class="combined-value">
              <span>${renderMeasurementValue(measurement.height, " cm", 1)}</span>
              <span>${renderMeasurementValue(measurement.weight, " kg", 1)}</span>
            </div>
          </td>
          <td>
            <div class="result-cell">
              <strong>${renderMeasurementValue(measurement.bmi, "", 1)}</strong>
              ${renderStatusBadge(
                measurement.bmi_category,
                measurement.bmi_status
              )}
            </div>
          </td>
          <td>
            <div class="result-cell">
              <strong>${escapeHtml(measurement.systolic)}/${escapeHtml(measurement.diastolic)}</strong>
              ${renderStatusBadge(
                measurement.blood_pressure_category,
                measurement.blood_pressure_status
              )}
            </div>
          </td>
          <td>
            <div class="result-cell">
              <strong>${renderMeasurementValue(
                measurement.blood_sugar,
                "",
                1
              )}</strong>
              ${renderStatusBadge(
                measurement.fasting_glucose_category,
                measurement.fasting_glucose_status
              )}
            </div>
          </td>
          <td>
            ${renderStatusBadge(
              measurement.overall_category,
              measurement.overall_status
            )}
          </td>
          <td>
            <div class="action-buttons">
              <button class="table-button detail-button" type="button">상세</button>
              <button class="danger-button delete-button" type="button">삭제</button>
            </div>
          </td>
        `;

        row
          .querySelector(".detail-button")
          .addEventListener("click", () => showDetail(measurement.id));

        row
          .querySelector(".delete-button")
          .addEventListener(
            "click",
            () => deleteMeasurement(
              measurement.id,
              measurement.date,
              user
            )
          );

        measurementTableBody.appendChild(row);
      });

      measurementPanel.scrollIntoView({
        behavior: "smooth",
        block: "start"
      });
    } catch (error) {
      showMessage(messageElement, error.message);
    }
  }

  async function deleteMeasurement(
    measurementId,
    measurementDate,
    user
  ) {
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
      await loadUserMeasurements(user);
      await loadUsers(searchInput.value.trim());
    } catch (error) {
      if (error.status === 401 || error.status === 403) {
        window.location.replace("/");
        return;
      }

      showMessage(messageElement, error.message);
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
      showMessage(messageElement, error.message);
    }
  }

  loadUsers();
});

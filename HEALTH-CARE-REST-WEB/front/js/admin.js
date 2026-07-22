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

        row.innerHTML = `
          <td>${escapeHtml(measurement.date)}</td>
          <td>${Number(measurement.height).toFixed(1)} cm</td>
          <td>${Number(measurement.weight).toFixed(1)} kg</td>
          <td>${escapeHtml(measurement.systolic)}/${escapeHtml(measurement.diastolic)}</td>
          <td>${Number(measurement.blood_sugar).toFixed(1)}</td>
          <td><button class="table-button" type="button">상세</button></td>
        `;

        row
          .querySelector("button")
          .addEventListener("click", () => showDetail(measurement.id));

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

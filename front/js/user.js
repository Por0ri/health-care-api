document.addEventListener("DOMContentLoaded", () => {
  const session = requireSession("user");

  if (!session) {
    return;
  }

  const accountLabel = document.querySelector("#account-label");
  const messageElement = document.querySelector("#message");
  const form = document.querySelector("#measurement-form");
  const tableBody = document.querySelector("#measurement-table-body");
  const emptyMessage = document.querySelector("#empty-message");
  const detailDialog = document.querySelector("#detail-dialog");
  const detailList = document.querySelector("#measurement-detail");
  const dateInput = document.querySelector("#measurement-date");

  accountLabel.textContent = `${session.account_id} 님`;
  dateInput.max = new Date().toISOString().slice(0, 10);
  dateInput.value = dateInput.max;

  document
    .querySelector("#logout-button")
    .addEventListener("click", logout);

  document
    .querySelector("#refresh-button")
    .addEventListener("click", loadMeasurements);

  document
    .querySelector("#dialog-close-button")
    .addEventListener("click", () => detailDialog.close());

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

      showMessage(messageElement, result.message, "success");
      form.reset();
      dateInput.value = dateInput.max;
      await loadMeasurements();
    } catch (error) {
      if (error.status === 401) {
        window.location.replace("/");
        return;
      }

      showMessage(messageElement, error.message);
    }
  });

  async function loadMeasurements() {
    hideMessage(messageElement);

    try {
      const result = await apiRequest("/measurements");
      const measurements = result.data.measurements;

      tableBody.innerHTML = "";
      emptyMessage.classList.toggle("hidden", measurements.length > 0);

      measurements.forEach((measurement) => {
        const row = document.createElement("tr");

        row.innerHTML = `
          <td>${escapeHtml(measurement.date)}</td>
          <td>${Number(measurement.height).toFixed(1)} cm</td>
          <td>${Number(measurement.weight).toFixed(1)} kg</td>
          <td>${escapeHtml(measurement.systolic)}/${escapeHtml(measurement.diastolic)}</td>
          <td>${Number(measurement.blood_sugar).toFixed(1)}</td>
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
            () => deleteMeasurement(measurement.id, measurement.date)
          );

        tableBody.appendChild(row);
      });
    } catch (error) {
      if (error.status === 401) {
        window.location.replace("/");
        return;
      }

      showMessage(messageElement, error.message);
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
      await loadMeasurements();
    } catch (error) {
      if (error.status === 401) {
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

  loadMeasurements();
});

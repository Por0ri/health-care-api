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
  const editDialog = document.querySelector("#edit-dialog");
  const editForm = document.querySelector("#edit-measurement-form");
  const editDateInput = document.querySelector("#edit-date");

  accountLabel.textContent = `${session.account_id} 님`;
  dateInput.max = new Date().toISOString().slice(0, 10);
  dateInput.value = dateInput.max;
  editDateInput.max = dateInput.max;

  document
    .querySelector("#logout-button")
    .addEventListener("click", logout);

  document
    .querySelector("#refresh-button")
    .addEventListener("click", loadMeasurements);

  document
    .querySelector("#dialog-close-button")
    .addEventListener("click", () => detailDialog.close());


  document
    .querySelector("#edit-dialog-close-button")
    .addEventListener("click", () => editDialog.close());

  document
    .querySelector("#edit-cancel-button")
    .addEventListener("click", () => editDialog.close());

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

      form.reset();
      dateInput.value = dateInput.max;
  editDateInput.max = dateInput.max;
      await loadMeasurements();
    } catch (error) {
      if (error.status === 401) {
        window.location.replace("/");
        return;
      }

      showMessage(messageElement, error.message);
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

      const measurement = result.data.measurement;
      const warnings = result.data.warnings || [];

      editDialog.close();

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
    try {
      const result = await apiRequest("/measurements");
      const measurements = result.data.measurements;

      tableBody.innerHTML = "";
      emptyMessage.classList.toggle("hidden", measurements.length > 0);

      measurements.forEach((measurement) => {
        const row = document.createElement("tr");
        row.className = "measurement-row";
        row.innerHTML = `
          <td>${escapeHtml(measurement.date)}</td>
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
              <button
                class="table-button detail-button"
                type="button"
              >
                상세
              </button>
              <button
                class="edit-button update-button"
                type="button"
              >
                수정
              </button>
              <button
                class="danger-button delete-button"
                type="button"
              >
                삭제
              </button>
            </div>
          </td>
        `;
        row
          .querySelector(".detail-button")
          .addEventListener("click", () => showDetail(measurement.id));

        row
          .querySelector(".update-button")
          .addEventListener("click", () => openEditDialog(measurement.id));

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


  async function openEditDialog(measurementId) {
    hideMessage(messageElement);

    try {
      const result = await apiRequest(`/measurements/${measurementId}`);
      const measurement = result.data.measurement;

      document.querySelector("#edit-measurement-id").value = measurement.id;
      document.querySelector("#edit-date").value = measurement.date;
      document.querySelector("#edit-height").value = measurement.height;
      document.querySelector("#edit-weight").value = measurement.weight;
      document.querySelector("#edit-systolic").value = measurement.systolic;
      document.querySelector("#edit-diastolic").value = measurement.diastolic;
      document.querySelector("#edit-blood-sugar").value = measurement.blood_sugar;
      document.querySelector("#edit-memo").value = measurement.memo || "";

      editDialog.showModal();
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

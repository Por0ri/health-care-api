document.addEventListener("DOMContentLoaded", () => {
  const existingSession = getStoredSession();

  if (existingSession?.role === "user") {
    window.location.replace("/user.html");
    return;
  }

  if (existingSession?.role === "admin") {
    window.location.replace("/admin.html");
    return;
  }

  const messageElement = document.querySelector("#message");
  const tabButtons = document.querySelectorAll(".tab-button");
  const tabPanels = document.querySelectorAll(".tab-panel");

  tabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const selectedTab = button.dataset.tab;

      tabButtons.forEach((item) => {
        item.classList.toggle("active", item === button);
      });

      tabPanels.forEach((panel) => {
        panel.classList.toggle(
          "active",
          panel.id === `${selectedTab}-form`
        );
      });

      hideMessage(messageElement);
    });
  });

  document
    .querySelector("#user-login-form")
    .addEventListener("submit", async (event) => {
      event.preventDefault();
      hideMessage(messageElement);

      const formData = new FormData(event.currentTarget);

      try {
        const result = await apiRequest("/sessions", {
          method: "POST",
          body: JSON.stringify({
            role: "user",
            account_id: formData.get("account_id"),
            pw: formData.get("pw")
          })
        });

        storeSession(result.data.session);
        window.location.replace("/user.html");
      } catch (error) {
        showMessage(messageElement, error.message);
      }
    });

  document
    .querySelector("#admin-login-form")
    .addEventListener("submit", async (event) => {
      event.preventDefault();
      hideMessage(messageElement);

      const formData = new FormData(event.currentTarget);

      try {
        const result = await apiRequest("/sessions", {
          method: "POST",
          body: JSON.stringify({
            role: "admin",
            account_id: formData.get("account_id"),
            pw: formData.get("pw")
          })
        });

        storeSession(result.data.session);
        window.location.replace("/admin.html");
      } catch (error) {
        showMessage(messageElement, error.message);
      }
    });

  document
    .querySelector("#signup-form")
    .addEventListener("submit", async (event) => {
      event.preventDefault();
      hideMessage(messageElement);

      const formData = new FormData(event.currentTarget);
      const password = formData.get("pw");
      const passwordConfirm = formData.get("pw_confirm");

      if (password !== passwordConfirm) {
        showMessage(messageElement, "비밀번호가 일치하지 않습니다.");
        return;
      }

      try {
        const result = await apiRequest("/users", {
          method: "POST",
          body: JSON.stringify({
            user_id: formData.get("user_id"),
            pw: password,
            name: formData.get("name"),
            birth: formData.get("birth")
          })
        });

        event.currentTarget.reset();
        tabButtons[0].click();
        showMessage(
          messageElement,
          `${result.message} 사용자 로그인 탭에서 로그인해 주세요.`,
          "success"
        );
      } catch (error) {
        showMessage(messageElement, error.message);
      }
    });
});

function showToast(message, tone = "info", timeout = 3200) {
  const root = document.getElementById("toast-root");
  if (!root) return;

  const node = document.createElement("div");
  node.className = "toast";
  node.dataset.tone = tone;
  node.textContent = message;
  root.append(node);

  window.setTimeout(() => {
    node.style.opacity = "0";
    node.style.transform = "translateY(8px)";
    window.setTimeout(() => node.remove(), 200);
  }, timeout);
}

window.splitboxToast = showToast;

document.querySelectorAll(".flash").forEach((node) => {
  window.setTimeout(() => {
    node.style.opacity = "0";
    node.style.transform = "translateY(-4px)";
    window.setTimeout(() => node.remove(), 200);
  }, 5200);
});

document.addEventListener("submit", (event) => {
  const message = event.target.dataset.confirm;
  if (message && !window.confirm(message)) {
    event.preventDefault();
  }
});


document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-send-pi]");
  if (!button) return;

  const status = document.querySelector("[data-pi-status]");
  button.disabled = true;
  if (status) status.textContent = "Queueing category…";

  try {
    const response = await fetch(
      `/api/categories/${button.dataset.sendPi}/send-to-pi`,
      { method: "POST" },
    );
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(body.detail || "Could not queue the category.");
    }
    if (status) status.textContent = body.message;
    showToast(body.message, "success", 4_500);
  } catch (error) {
    if (status) status.textContent = error.message;
    showToast(error.message, "error", 5_000);
  } finally {
    button.disabled = false;
  }
});

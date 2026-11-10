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

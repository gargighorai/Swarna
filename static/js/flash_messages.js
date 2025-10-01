document.addEventListener("DOMContentLoaded", function () {
  const alerts = document.querySelectorAll(".alert");
  alerts.forEach((alert) => {
    setTimeout(() => {
      alert.classList.add("fade");
      setTimeout(() => alert.remove(), 500);
    }, 2000); // hides flash messages after 3s
  });
});
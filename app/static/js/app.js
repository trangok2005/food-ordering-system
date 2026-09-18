(function () {
  "use strict";

  document.addEventListener("submit", function (event) {
    const form = event.target.closest("form[data-confirm]");
    if (form && !window.confirm(form.dataset.confirm)) event.preventDefault();
  });

  document.querySelectorAll("[data-geolocation]").forEach(function (element) {
    window.TvTFood.initGeolocation({
      button: "#" + element.id,
      status: element.dataset.status,
      latitude: element.dataset.latitude,
      longitude: element.dataset.longitude,
      precision: element.dataset.precision ? Number(element.dataset.precision) : null,
      successMessage: element.dataset.success,
      errorMessage: element.dataset.error,
    });
  });

  const badge = document.getElementById("cartId");
  if (!badge || !badge.dataset.endpoint) return;

  const endpoint = badge.dataset.endpoint;

  function render(quantity) {
    badge.textContent = quantity;
    badge.classList.toggle("d-none", quantity <= 0);
  }

  fetch(endpoint)
    .then((res) => {
      if (!res.ok) throw new Error(res.status);
      return res.json();
    })
    .then((data) => {
      render(Number(data.total_quantity) || 0);
    })
    .catch(() => {
      /* giữ giá trị server render, không hiển thị lỗi */
    });
})();

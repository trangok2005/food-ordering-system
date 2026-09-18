(function () {
  "use strict";

  function initGeolocation(config) {
    const button = document.querySelector(config.button);
    const status = document.querySelector(config.status);
    const latitude = document.querySelector(config.latitude);
    const longitude = document.querySelector(config.longitude);
    if (!button || !status || !latitude || !longitude) return;

    button.addEventListener("click", function () {
      if (!navigator.geolocation) {
        status.textContent = "Trình duyệt không hỗ trợ định vị.";
        status.className = "location-status is-error";
        return;
      }

      button.disabled = true;
      status.textContent = "Đang xác định vị trí...";
      status.className = "location-status is-loading";
      navigator.geolocation.getCurrentPosition(
        function (position) {
          const precision = Number.isInteger(config.precision) ? config.precision : null;
          latitude.value = precision === null
            ? position.coords.latitude
            : position.coords.latitude.toFixed(precision);
          longitude.value = precision === null
            ? position.coords.longitude
            : position.coords.longitude.toFixed(precision);
          status.textContent = config.successMessage || "Đã lấy vị trí hiện tại.";
          status.className = "location-status is-success";
          button.disabled = false;
          if (typeof config.onSuccess === "function") config.onSuccess(position);
        },
        function () {
          status.textContent = config.errorMessage || "Không lấy được vị trí. Vui lòng thử lại hoặc nhập tay.";
          status.className = "location-status is-error";
          button.disabled = false;
        },
        { enableHighAccuracy: true, timeout: 8000, maximumAge: 300000 }
      );
    });
  }

  window.TvTFood = { initGeolocation: initGeolocation };
})();

(function () {
  const form = document.getElementById("checkout-form");
  if (!form) return;

  const confirmBtn = document.getElementById("confirm-order");
  const useLocationBtn = document.getElementById("use-location");
  const locationStatus = document.getElementById("location-status");
  const latInput = document.getElementById("lat");
  const lngInput = document.getElementById("lng");

  if (confirmBtn) {
    confirmBtn.addEventListener("click", () => {
      if (confirmBtn.disabled) return;
      if (!form.checkValidity()) {
        form.reportValidity();
        return;
      }
      form.submit();
    });
  }

  if (useLocationBtn) {
    useLocationBtn.addEventListener("click", () => {
      if (!navigator.geolocation) {
        locationStatus.textContent = "Trình duyệt không hỗ trợ định vị.";
        return;
      }
      locationStatus.textContent = "Đang xác định vị trí...";
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          latInput.value = pos.coords.latitude;
          lngInput.value = pos.coords.longitude;
          locationStatus.textContent = "Đã lấy vị trí. Hệ thống sẽ kiểm tra bán kính giao hàng.";
        },
        () => {
          locationStatus.textContent = "Không lấy được vị trí (bạn có thể bỏ qua, sẽ không kiểm tra bán kính).";
        },
        { enableHighAccuracy: true, timeout: 8000, maximumAge: 300000 }
      );
    });
  }
})();
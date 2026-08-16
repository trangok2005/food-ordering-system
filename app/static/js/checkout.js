const COUNTDOWN_SECONDS = 10;

(function () {
  const form = document.getElementById("checkout-form");
  if (!form) return;

  const confirmBtn = document.getElementById("confirm-order");
  const modalEl = document.getElementById("countdownModal");
  const countdownEl = document.getElementById("countdown-number");
  const cancelBtn = document.getElementById("cancel-countdown");
  const useLocationBtn = document.getElementById("use-location");
  const locationStatus = document.getElementById("location-status");
  const latInput = document.getElementById("lat");
  const lngInput = document.getElementById("lng");

  let timerId = null;
  let modal = null;
  if (window.bootstrap && modalEl) {
    modal = new window.bootstrap.Modal(modalEl);
  }

  function stopTimer() {
    if (timerId) {
      clearInterval(timerId);
      timerId = null;
    }
  }

  function startCountdown() {
    let remaining = COUNTDOWN_SECONDS;
    countdownEl.textContent = remaining;
    if (modal) modal.show();

    stopTimer();
    timerId = setInterval(() => {
      remaining -= 1;
      if (remaining > 0) {
        countdownEl.textContent = remaining;
        return;
      }
      stopTimer();
      if (modal) modal.hide();
      form.submit();
    }, 1000);
  }

  if (confirmBtn) {
    confirmBtn.addEventListener("click", () => {
      if (confirmBtn.disabled) return;
      if (!form.checkValidity()) {
        form.reportValidity();
        return;
      }
      startCountdown();
    });
  }

  if (cancelBtn) {
    cancelBtn.addEventListener("click", () => {
      stopTimer();
      if (modal) modal.hide();
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
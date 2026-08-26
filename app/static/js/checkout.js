(function () {
  const form = document.getElementById("checkout-form");
  if (!form) return;

  const confirmBtn = document.getElementById("confirm-order");
  const useLocationBtn = document.getElementById("use-location");
  const locationStatus = document.getElementById("location-status");
  const latInput = document.getElementById("lat");
  const lngInput = document.getElementById("lng");

  // Cửa sổ hủy miễn phí 10 giây (Quy tắc bắt buộc #5 - Project Charter):
  // sau khi bấm "Đặt hàng", khách có 10 giây để hủy miễn phí; hết giờ,
  // hệ thống TỰ ĐỘNG chuyển sang cổng thanh toán và không hỗ trợ hủy nữa.
  const FREE_CANCEL_SECONDS = 10;
  let countdownTimer = null;

  function startFreeCancelWindow() {
    const modalEl = document.getElementById("freeCancelModal");
    if (!modalEl) {
      form.submit();
      return;
    }
    const counter = document.getElementById("cancelCountdown");
    let secondsLeft = FREE_CANCEL_SECONDS;
    counter.textContent = secondsLeft;

    const modal = new bootstrap.Modal(modalEl);
    modal.show();

    clearInterval(countdownTimer);
    countdownTimer = setInterval(() => {
      secondsLeft -= 1;
      if (secondsLeft <= 0) {
        clearInterval(countdownTimer);
        modal.hide();
        form.submit();
        return;
      }
      counter.textContent = secondsLeft;
    }, 1000);
  }

  function stopFreeCancelWindow() {
    clearInterval(countdownTimer);
  }

  if (confirmBtn) {
    confirmBtn.addEventListener("click", () => {
      if (confirmBtn.disabled) return;
      if (!form.checkValidity()) {
        form.reportValidity();
        return;
      }
      startFreeCancelWindow();
    });
  }

  const freeCancelBtn = document.getElementById("freeCancelBtn");
  if (freeCancelBtn) {
    freeCancelBtn.addEventListener("click", () => {
      stopFreeCancelWindow();
      bootstrap.Modal.getInstance(document.getElementById("freeCancelModal")).hide();
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
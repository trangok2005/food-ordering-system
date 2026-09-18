(function () {
  const form = document.getElementById("checkout-form");
  if (!form) return;

  const confirmBtn = document.getElementById("confirm-order");
  // khách có 10 giây hủy trước khi sang cổng thanh toán
  const FREE_CANCEL_SECONDS = 10;
  let countdownTimer = null;
  let isSubmitting = false;
  const modalEl = document.getElementById("freeCancelModal");
  const modal = modalEl && window.bootstrap ? new bootstrap.Modal(modalEl) : null;

  function startFreeCancelWindow() {
    if (!modal) {
      isSubmitting = true;
      form.submit();
      return;
    }
    const counter = document.getElementById("cancelCountdown");
    if (!counter) {
      form.submit();
      return;
    }
    let secondsLeft = FREE_CANCEL_SECONDS;
    counter.textContent = secondsLeft;

    confirmBtn.disabled = true;
    modal.show();

    clearInterval(countdownTimer);
    countdownTimer = setInterval(() => {
      secondsLeft -= 1;
      if (secondsLeft <= 0) {
        clearInterval(countdownTimer);
        isSubmitting = true;
        modal.hide();
        form.submit();
        return;
      }
      counter.textContent = secondsLeft;
    }, 1000);
  }

  function stopFreeCancelWindow() {
    clearInterval(countdownTimer);
    countdownTimer = null;
    if (!isSubmitting && confirmBtn) confirmBtn.disabled = false;
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
      if (modal) modal.hide();
    });
  }

  if (modalEl) modalEl.addEventListener("hidden.bs.modal", stopFreeCancelWindow);

  window.TvTFood.initGeolocation({
    button: "#use-location",
    status: "#location-status",
    latitude: "#lat",
    longitude: "#lng",
    successMessage: "Đã lấy vị trí. Hệ thống sẽ kiểm tra bán kính giao hàng.",
    errorMessage: "Không lấy được vị trí. Vui lòng cấp quyền định vị và thử lại.",
    onSuccess: function () {
      if (confirmBtn && confirmBtn.dataset.blockingIssues !== "true") {
        confirmBtn.disabled = false;
      }
    },
  });
})();

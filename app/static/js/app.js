(function () {
  const badge = document.getElementById("cartId");
  if (!badge) return;

  const endpoint = badge.dataset.endpoint || "/cart/api/stats";

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
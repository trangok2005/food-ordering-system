(() => {
  "use strict";

  const cart = document.querySelector("[data-pairing-cart]");
  if (!cart) return;

  const formatPrice = new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency: "VND",
  });

  function message(panel, text, className = "text-muted") {
    panel.replaceChildren();
    const element = document.createElement("p");
    element.className = `small mb-0 ${className}`;
    element.textContent = text;
    panel.appendChild(element);
  }

  async function refreshCart() {
    const response = await fetch(window.location.href, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
    if (!response.ok) throw new Error("Không thể cập nhật giao diện giỏ hàng");

    const documentCopy = new DOMParser().parseFromString(
      await response.text(),
      "text/html",
    );
    const updatedCart = documentCopy.querySelector("[data-pairing-cart]");
    if (!updatedCart) throw new Error("Không thể cập nhật giao diện giỏ hàng");
    cart.innerHTML = updatedCart.innerHTML;
  }

  async function addSuggestion(dish, button, panel) {
    button.disabled = true;
    button.textContent = "Đang thêm...";

    const body = new FormData();
    body.append("_csrf_token", cart.dataset.csrfToken);
    body.append("dish_id", dish.id);
    body.append("quantity", "1");

    try {
      const response = await fetch(cart.dataset.addUrl, {
        method: "POST",
        headers: { "X-Requested-With": "XMLHttpRequest" },
        body,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Không thể thêm món");

      button.textContent = "Đã thêm";
      const badge = document.getElementById("cartId");
      if (badge) {
        badge.textContent = data.cart.total_quantity;
        badge.classList.toggle("d-none", data.cart.total_quantity <= 0);
      }
      try {
        await refreshCart();
      } catch (_error) {
        const total = document.querySelector("[data-cart-total]");
        if (total) total.textContent = formatPrice.format(data.cart.total_amount);
      }
    } catch (error) {
      button.disabled = false;
      button.textContent = "Thêm vào giỏ";
      message(panel, error.message, "text-danger");
    }
  }

  function renderSuggestions(panel, dishes) {
    panel.replaceChildren();
    if (!dishes.length) {
      message(panel, "Chưa có món đi kèm phù hợp.");
      return;
    }

    const list = document.createElement("div");
    list.className = "pairing-list";
    dishes.forEach((dish) => {
      const item = document.createElement("div");
      item.className = "pairing-item";

      if (dish.image) {
        const image = document.createElement("img");
        image.className = "pairing-item-image";
        image.src = dish.image;
        image.alt = dish.name;
        item.appendChild(image);
      }

      const info = document.createElement("div");
      info.className = "pairing-item-info";
      const name = document.createElement("div");
      name.className = "fw-semibold";
      name.textContent = dish.name;
      const price = document.createElement("div");
      price.className = "small text-muted";
      price.textContent = formatPrice.format(dish.price);
      info.append(name, price);

      const addButton = document.createElement("button");
      addButton.type = "button";
      addButton.className = "btn btn-outline-primary btn-sm";
      addButton.textContent = "Thêm vào giỏ";
      addButton.addEventListener("click", () => {
        addSuggestion(dish, addButton, panel);
      });
      item.append(info, addButton);
      list.appendChild(item);
    });
    panel.appendChild(list);
  }

  cart.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-pairing-toggle]");
    if (!button) return;

    const row = document.getElementById(button.dataset.target);
    const panel = row.querySelector("[data-pairing-panel]");
    const opening = row.classList.contains("d-none");
    row.classList.toggle("d-none", !opening);
    button.setAttribute("aria-expanded", String(opening));
    button.querySelector("span").textContent = opening ? "▲" : "▼";

    if (!opening || panel.dataset.loaded === "true") return;
    message(panel, "Đang tải gợi ý...");

    try {
      const response = await fetch(button.dataset.endpoint, {
        headers: { Accept: "application/json" },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Không thể tải gợi ý");
      panel.dataset.loaded = "true";
      renderSuggestions(panel, data.suggestions);
    } catch (error) {
      message(panel, error.message, "text-danger");
    }
  });
})();

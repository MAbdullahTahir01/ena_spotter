(function () {
  const map = L.map("map").setView([39.8283, -98.5795], 4); // center of US
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
    className: "map-tiles-dark",
  }).addTo(map);

  let routeLayer = null;
  let markerLayer = L.layerGroup().addTo(map);

  const form = document.getElementById("route-form");
  const submitBtn = document.getElementById("submit-btn");
  const errorAlert = document.getElementById("error-alert");
  const summaryRow = document.getElementById("summary-row");
  const summaryDisclaimer = document.getElementById("summary-disclaimer");

  const ENGINE_LABELS = { osrm: "OSRM", classic_a_star: "Classic A*" };

  function setupCombobox(inputId, menuId) {
    const input = document.getElementById(inputId);
    const menu = document.getElementById(menuId);
    let debounceHandle = null;
    let activeIndex = -1;
    let items = [];

    function closeMenu() {
      menu.classList.add("hidden");
      menu.innerHTML = "";
      items = [];
      activeIndex = -1;
      input.setAttribute("aria-expanded", "false");
    }

    function highlight(index) {
      const children = Array.from(menu.children);
      children.forEach(function (child, i) {
        child.classList.toggle("active", i === index);
      });
      activeIndex = index;
    }

    function selectItem(label) {
      input.value = label;
      closeMenu();
    }

    function renderResults(results) {
      items = results;
      if (!results.length) {
        closeMenu();
        return;
      }
      menu.innerHTML = "";
      results.forEach(function (result) {
        const el = document.createElement("button");
        el.type = "button";
        el.className = "combo-option";
        el.textContent = result.label;
        el.addEventListener("mousedown", function (event) {
          event.preventDefault();
          selectItem(result.label);
        });
        menu.appendChild(el);
      });
      menu.classList.remove("hidden");
      input.setAttribute("aria-expanded", "true");
      activeIndex = -1;
    }

    input.addEventListener("input", function () {
      const query = input.value.trim();
      if (debounceHandle) {
        clearTimeout(debounceHandle);
      }
      if (query.length < 2) {
        closeMenu();
        return;
      }
      debounceHandle = setTimeout(async function () {
        try {
          const response = await fetch("/api/cities/?q=" + encodeURIComponent(query));
          if (!response.ok) {
            return;
          }
          const body = await response.json();
          renderResults((body.data && body.data.results) || []);
        } catch (err) {
          closeMenu();
        }
      }, 200);
    });

    input.addEventListener("keydown", function (event) {
      if (menu.classList.contains("hidden") || !items.length) {
        return;
      }
      if (event.key === "ArrowDown") {
        event.preventDefault();
        highlight(Math.min(activeIndex + 1, items.length - 1));
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        highlight(Math.max(activeIndex - 1, 0));
      } else if (event.key === "Enter") {
        if (activeIndex >= 0) {
          event.preventDefault();
          selectItem(items[activeIndex].label);
        }
      } else if (event.key === "Escape") {
        closeMenu();
      }
    });

    input.addEventListener("blur", closeMenu);
  }

  setupCombobox("start", "start-menu");
  setupCombobox("finish", "finish-menu");

  function showError(message) {
    errorAlert.textContent = message;
    errorAlert.classList.remove("hidden");
  }

  function clearError() {
    errorAlert.classList.add("hidden");
    errorAlert.textContent = "";
  }

  function formatCurrency(value) {
    return "$" + value.toFixed(2);
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    clearError();
    summaryRow.classList.add("hidden");
    summaryDisclaimer.classList.add("hidden");
    submitBtn.disabled = true;
    submitBtn.textContent = "Loading…";

    const start = document.getElementById("start").value.trim();
    const finish = document.getElementById("finish").value.trim();

    if (start.toLowerCase() === finish.toLowerCase()) {
      showError("Start and finish must be different locations.");
      submitBtn.disabled = false;
      submitBtn.textContent = "Find route";
      return;
    }

    try {
      const response = await fetch("/api/route/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ start: start, finish: finish }),
      });
      const body = await response.json();

      if (!response.ok || !body.status) {
        showError(body.message || "Something went wrong.");
        return;
      }

      renderResult(body.data);
    } catch (err) {
      showError("Network error: " + err.message);
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Find route";
    }
  });

  function renderResult(data) {
    document.getElementById("summary-distance").textContent =
      data.distance_miles.toFixed(1) + " mi";
    document.getElementById("summary-gallons").textContent =
      data.total_gallons.toFixed(2) + " gal";
    document.getElementById("summary-cost").textContent =
      formatCurrency(data.total_cost);
    document.getElementById("summary-engine").textContent =
      ENGINE_LABELS[data.engine] || data.engine;
    summaryRow.classList.remove("hidden");
    summaryDisclaimer.classList.remove("hidden");

    if (routeLayer) {
      map.removeLayer(routeLayer);
    }
    markerLayer.clearLayers();

    const latlngs = data.route_geometry.map(function (pair) {
      return [pair[1], pair[0]]; // [lon, lat] -> [lat, lon]
    });
    routeLayer = L.polyline(latlngs, { color: "#ffb703", weight: 4 }).addTo(map);
    map.fitBounds(routeLayer.getBounds(), { padding: [20, 20] });

    data.fuel_stops.forEach(function (stop) {
      const marker = L.marker([stop.latitude, stop.longitude]).addTo(markerLayer);
      marker.bindPopup(
        "<strong>" + escapeHtml(stop.name) + "</strong><br>" +
        escapeHtml(stop.address) + ", " + escapeHtml(stop.city) + ", " + escapeHtml(stop.state) + "<br>" +
        "Price: " + formatCurrency(stop.price) + "/gal<br>" +
        "Bought: " + stop.gallons_bought.toFixed(2) + " gal (" +
        formatCurrency(stop.cost) + ")"
      );
    });
  }
})();

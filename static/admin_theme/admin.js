/* Admin dizayni: son maydonlaridagi brauzer ▲▼ tugmachalari o'rniga  −  [ son ]  +  */
(function () {
  "use strict";

  function makeButton(dir, label) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "ds-stepper__btn";
    btn.dataset.step = dir;
    btn.setAttribute("aria-label", label);
    btn.tabIndex = -1; // klaviatura bilan ↑/↓ tugmalari ishlaydi, Tab tugmachalarga to'xtamaydi
    btn.textContent = dir === "up" ? "+" : "−";
    return btn;
  }

  function enhance(root) {
    (root || document).querySelectorAll('input[type="number"]').forEach(function (input) {
      if (input.closest(".ds-stepper") || input.type !== "number") return;
      var wrap = document.createElement("span");
      wrap.className = "ds-stepper";
      input.parentNode.insertBefore(wrap, input);
      wrap.appendChild(makeButton("down", "Kamaytirish"));
      wrap.appendChild(input);
      wrap.appendChild(makeButton("up", "Ko'paytirish"));
      sync(wrap);
    });
  }

  function sync(wrap) {
    var input = wrap.querySelector("input");
    var value = input.value === "" ? null : Number(input.value);
    var min = input.min === "" ? null : Number(input.min);
    var max = input.max === "" ? null : Number(input.max);
    wrap.querySelector('[data-step="down"]').disabled = input.disabled || (min !== null && value !== null && value <= min);
    wrap.querySelector('[data-step="up"]').disabled = input.disabled || (max !== null && value !== null && value >= max);
  }

  // Hodisalar delegatsiyasi — Django inline qo'shganda nusxalangan qatorlarda ham ishlaydi
  document.addEventListener("click", function (event) {
    var btn = event.target.closest(".ds-stepper__btn");
    if (!btn) return;
    var wrap = btn.closest(".ds-stepper");
    var input = wrap.querySelector("input");
    if (input.value === "") input.value = input.min !== "" ? input.min : "0";
    else if (btn.dataset.step === "up") input.stepUp();
    else input.stepDown();
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    sync(wrap);
  });

  document.addEventListener("input", function (event) {
    var wrap = event.target.closest && event.target.closest(".ds-stepper");
    if (wrap) sync(wrap);
  });

  document.addEventListener("formset:added", function (event) { enhance(event.target); });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { enhance(); });
  } else {
    enhance();
  }
})();

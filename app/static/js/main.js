/* Skillected Jobs — progressive enhancement only; pages work without JS. */
document.addEventListener("click", function (e) {
  const btn = e.target.closest("[data-copy]");
  if (!btn) return;
  const text = btn.getAttribute("data-copy");
  navigator.clipboard.writeText(text).then(function () {
    const old = btn.textContent;
    btn.textContent = "✓ Copied";
    setTimeout(function () { btn.textContent = old; }, 1600);
  }).catch(function () { /* clipboard unavailable */ });
});

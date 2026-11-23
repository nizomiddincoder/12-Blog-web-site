(function () {
  "use strict";

  // Mobil menyu
  var navToggle = document.getElementById("nav-toggle");
  var nav = document.getElementById("site-nav");
  if (navToggle && nav) {
    navToggle.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      navToggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
    nav.addEventListener("click", function (e) {
      if (e.target.closest("a")) nav.classList.remove("open");
    });
  }

  // Logotiplar lentasi: logotiplar kam bo'lsa ham ekranni to'ldirsin, tezlik bir xil bo'lsin
  var MARQUEE_SPEED = 50; // px/soniya
  document.querySelectorAll(".js-marquee").forEach(function (marquee) {
    var groups = marquee.querySelectorAll(".logo-group");
    if (groups.length !== 2) return;
    var originals = Array.prototype.slice.call(groups[0].children);
    if (!originals.length) return;
    function fill() {
      var need = Math.max(marquee.clientWidth, window.screen.width || 0);
      var guard = 0;
      while (groups[0].scrollWidth < need && guard++ < 20) {
        originals.forEach(function (li) {
          var copy = li.cloneNode(true);
          copy.setAttribute("aria-hidden", "true");
          copy.querySelectorAll("a").forEach(function (a) { a.tabIndex = -1; });
          copy.querySelectorAll("img").forEach(function (img) { img.alt = ""; });
          groups[0].appendChild(copy);
          groups[1].appendChild(copy.cloneNode(true));
        });
      }
      marquee.style.setProperty("--marquee-duration", Math.max(groups[0].scrollWidth / MARQUEE_SPEED, 10) + "s");
    }
    fill();
    window.addEventListener("resize", fill);
  });

  // Minimal video pleyer
  function fmt(t) {
    t = Math.floor(t || 0);
    return Math.floor(t / 60) + ":" + String(t % 60).padStart(2, "0");
  }
  document.querySelectorAll(".js-player").forEach(function (player) {
    var video = player.querySelector("video");
    var toggleIcon = player.querySelector('[data-act="toggle"] i');
    var muteIcon = player.querySelector('[data-act="mute"] i');
    var time = player.querySelector('[data-el="time"]');
    var track = player.querySelector('[data-el="track"]');
    var fill = player.querySelector('[data-el="fill"]');

    function toggle() { if (video.paused) video.play(); else video.pause(); }
    player.querySelector(".player-big").addEventListener("click", toggle);
    video.addEventListener("click", toggle);
    player.querySelector('[data-act="toggle"]').addEventListener("click", toggle);
    player.querySelector('[data-act="mute"]').addEventListener("click", function () {
      video.muted = !video.muted;
      muteIcon.className = video.muted ? "bi bi-volume-mute" : "bi bi-volume-up";
    });
    player.querySelector('[data-act="full"]').addEventListener("click", function () {
      if (document.fullscreenElement) document.exitFullscreen();
      else if (player.requestFullscreen) player.requestFullscreen();
      else if (video.webkitEnterFullscreen) video.webkitEnterFullscreen();
    });
    track.addEventListener("click", function (e) {
      if (!video.duration) return;
      var rect = track.getBoundingClientRect();
      video.currentTime = ((e.clientX - rect.left) / rect.width) * video.duration;
    });
    video.addEventListener("play", function () {
      player.classList.add("is-playing", "is-started");
      toggleIcon.className = "bi bi-pause-fill";
    });
    video.addEventListener("pause", function () {
      player.classList.remove("is-playing");
      toggleIcon.className = "bi bi-play-fill";
    });
    video.addEventListener("timeupdate", function () {
      time.textContent = fmt(video.currentTime) + " / " + fmt(video.duration);
      fill.style.width = video.duration ? (video.currentTime / video.duration) * 100 + "%" : "0";
    });
  });

  // Bir video ijro etilsa, boshqalari to'xtaydi
  document.addEventListener("play", function (e) {
    document.querySelectorAll("video").forEach(function (v) {
      if (v !== e.target && !v.paused) v.pause();
    });
  }, true);

  // Havolani nusxalash
  document.querySelectorAll(".js-copy").forEach(function (btn) {
    btn.addEventListener("click", function () {
      if (!navigator.clipboard) return;
      navigator.clipboard.writeText(btn.dataset.url).then(function () {
        var icon = btn.querySelector("i");
        icon.className = "bi bi-check2";
        setTimeout(function () { icon.className = "bi bi-link-45deg"; }, 1500);
      });
    });
  });

  // Lightbox — rasmni asl o'lchamida ko'rish
  var box = document.getElementById("lightbox");
  var images = Array.prototype.slice.call(document.querySelectorAll(".js-lightbox"));
  if (!box || !images.length) return;
  var boxImg = box.querySelector("img");
  var index = 0;
  function show(i) {
    index = (i + images.length) % images.length;
    boxImg.src = images[index].currentSrc || images[index].src;
    boxImg.alt = images[index].alt;
    box.hidden = false;
    document.body.style.overflow = "hidden";
    var multi = images.length > 1 ? "" : "none";
    box.querySelector(".lightbox-prev").style.display = multi;
    box.querySelector(".lightbox-next").style.display = multi;
  }
  function hide() {
    box.hidden = true;
    boxImg.src = "";
    document.body.style.overflow = "";
  }
  images.forEach(function (img, i) { img.addEventListener("click", function () { show(i); }); });
  box.querySelector(".lightbox-close").addEventListener("click", hide);
  box.querySelector(".lightbox-prev").addEventListener("click", function (e) { e.stopPropagation(); show(index - 1); });
  box.querySelector(".lightbox-next").addEventListener("click", function (e) { e.stopPropagation(); show(index + 1); });
  box.addEventListener("click", function (e) { if (e.target === box) hide(); });
  document.addEventListener("keydown", function (e) {
    if (box.hidden) return;
    if (e.key === "Escape") hide();
    if (e.key === "ArrowLeft") show(index - 1);
    if (e.key === "ArrowRight") show(index + 1);
  });
})();

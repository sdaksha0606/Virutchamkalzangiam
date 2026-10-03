/* ═══════════════════════════════════════════════════════════════════════════
   Virutcham Magalir Munnetra Kalzangiam — Main JS
   Open Source | MIT License
═══════════════════════════════════════════════════════════════════════════ */

"use strict";

// ── Navbar scroll behaviour ──────────────────────────────────────────────────
const navbar = document.getElementById("navbar");
if (navbar) {
  const accessibilityBar = document.querySelector(".a11y-bar");
  const updateHeaderGeometry = () => {
    const accessibilityHeight = accessibilityBar?.getBoundingClientRect().height ?? 0;
    const navbarHeight = navbar.getBoundingClientRect().height;
    document.documentElement.style.setProperty("--a11y-bar-height", `${accessibilityHeight}px`);
    document.documentElement.style.setProperty("--navbar-height", `${navbarHeight}px`);
    navbar.classList.toggle("scrolled", window.scrollY >= accessibilityHeight);
  };

  updateHeaderGeometry();
  window.addEventListener("resize", updateHeaderGeometry, { passive: true });
  if (window.ResizeObserver && accessibilityBar) {
    const headerObserver = new ResizeObserver(updateHeaderGeometry);
    headerObserver.observe(accessibilityBar);
    headerObserver.observe(navbar.querySelector(".nav-inner"));
  }

  const onScroll = () => {
    const accessibilityHeight = accessibilityBar?.getBoundingClientRect().height ?? 0;
    navbar.classList.toggle("scrolled", window.scrollY >= accessibilityHeight);
  };
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
}

// ── Mobile hamburger ─────────────────────────────────────────────────────────
const hamburger = document.getElementById("hamburger");
if (hamburger) {
  const navLinks = document.querySelector(".nav-links");
  hamburger.addEventListener("click", () => {
    const isOpen = navLinks.classList.toggle("open");
    navbar.classList.toggle("open", isOpen);
    hamburger.setAttribute("aria-expanded", String(isOpen));
  });
  // close on link click
  document.querySelectorAll(".nav-links a").forEach(link => {
    link.addEventListener("click", () => {
      navLinks.classList.remove("open");
      navbar.classList.remove("open");
      hamburger.setAttribute("aria-expanded", "false");
    });
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && navLinks.classList.contains("open")) {
      navLinks.classList.remove("open");
      navbar.classList.remove("open");
      hamburger.setAttribute("aria-expanded", "false");
      hamburger.focus();
    }
  });
}

// ── Hero slideshow ───────────────────────────────────────────────────────────
let currentSlide = 0;
const slides     = document.querySelectorAll(".slide");
const dots       = document.querySelectorAll(".dot");

function goSlide(n) {
  slides[currentSlide].classList.remove("active");
  dots[currentSlide].classList.remove("active");
  currentSlide = (n + slides.length) % slides.length;
  slides[currentSlide].classList.add("active");
  dots[currentSlide].classList.add("active");
}

if (slides.length > 0) {
  setInterval(() => goSlide(currentSlide + 1), 5000);
}

// ── Scroll reveal ────────────────────────────────────────────────────────────
const revealObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry, i) => {
      if (entry.isIntersecting) {
        // stagger children within same parent
        const siblings = entry.target.parentElement.querySelectorAll("[data-reveal]");
        let delay = 0;
        siblings.forEach((sib, idx) => {
          if (sib === entry.target) delay = idx * 120;
        });
        setTimeout(() => entry.target.classList.add("visible"), delay);
        revealObserver.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.12, rootMargin: "0px 0px -60px 0px" }
);

document.querySelectorAll("[data-reveal]").forEach(el => revealObserver.observe(el));

// ── Animated counters ────────────────────────────────────────────────────────
function animateCounter(el) {
  const target   = parseInt(el.dataset.count, 10);
  const duration = 1800;
  const start    = performance.now();
  const easeOut  = t => 1 - Math.pow(1 - t, 3);

  function tick(now) {
    const elapsed  = now - start;
    const progress = Math.min(elapsed / duration, 1);
    el.textContent = Math.floor(easeOut(progress) * target).toLocaleString("en-IN");
    if (progress < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

const counterObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        animateCounter(entry.target);
        counterObserver.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.5 }
);

document.querySelectorAll("[data-count]").forEach(el => counterObserver.observe(el));

// ── Contact form (simple client-side handler) ────────────────────────────────
const contactForm = document.getElementById("contactForm");
if (contactForm) {
  contactForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = contactForm.querySelector("button[type=submit]");
    const orig = btn.textContent;
    btn.textContent = window.PUBLIC_UI?.contact_sending || "Sending…";
    btn.disabled = true;

    // Simulate / replace with real endpoint
    await new Promise(r => setTimeout(r, 1200));

    btn.textContent = window.PUBLIC_UI?.contact_sent || "✓ Message Sent!";
    btn.style.background = "linear-gradient(135deg, #1a7a3c, #145a2e)";
    contactForm.reset();

    setTimeout(() => {
      btn.textContent = orig;
      btn.style.background = "";
      btn.disabled = false;
    }, 4000);
  });
}

// ── Smooth scroll for anchor links ───────────────────────────────────────────
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener("click", (e) => {
    const target = document.querySelector(anchor.getAttribute("href"));
    if (target) {
      e.preventDefault();
      const navH = navbar ? navbar.offsetHeight : 0;
      const top  = target.getBoundingClientRect().top + window.scrollY - navH - 16;
      window.scrollTo({ top, behavior: "smooth" });
    }
  });
});

// ── Active nav link highlight on scroll ──────────────────────────────────────
const sections   = document.querySelectorAll("section[id]");
const navAnchors = document.querySelectorAll(".nav-links a[href^='#']");

const sectionObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        navAnchors.forEach(a => {
          a.style.color = "";
          if (a.getAttribute("href") === `#${entry.target.id}`) {
            a.style.color = "var(--green-400)";
          }
        });
      }
    });
  },
  { rootMargin: "-30% 0px -60% 0px" }
);

sections.forEach(s => sectionObserver.observe(s));

// ── Accessibility: Font Size & High Contrast ─────────────────────────────────
(function() {
  const STORAGE_KEY_SIZE     = "virutcham_font_size";
  const STORAGE_KEY_CONTRAST = "virutcham_contrast";

  const sizeSteps = ["normal", "large", "xlarge"];
  let currentSizeIdx = sizeSteps.indexOf(localStorage.getItem(STORAGE_KEY_SIZE) || "normal");
  if (currentSizeIdx < 0) currentSizeIdx = 0;

  function applySize() {
    document.body.style.fontSize = currentSizeIdx === 0 ? "" :
      currentSizeIdx === 1 ? "18px" : "20px";
  }
  applySize();

  window.changeFontSize = function(direction) {
    currentSizeIdx = Math.min(2, Math.max(0, currentSizeIdx + direction));
    localStorage.setItem(STORAGE_KEY_SIZE, sizeSteps[currentSizeIdx]);
    applySize();
  };

  // High contrast
  let contrastOn = localStorage.getItem(STORAGE_KEY_CONTRAST) === "on";
  function applyContrast() {
    document.body.classList.toggle("high-contrast", contrastOn);
    const btn = document.getElementById("contrastBtn");
    if (btn) btn.classList.toggle("active", contrastOn);
  }
  applyContrast();

  window.toggleContrast = function() {
    contrastOn = !contrastOn;
    localStorage.setItem(STORAGE_KEY_CONTRAST, contrastOn ? "on" : "off");
    applyContrast();
  };
})();

import { useEffect, useRef } from "react";

// Cloudflare Turnstile. The default site key is Cloudflare's public test key (always passes);
// set VITE_TURNSTILE_SITEKEY at build time for production.
const SITE_KEY = import.meta.env.VITE_TURNSTILE_SITEKEY || "1x00000000000000000000AA";
const SCRIPT_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

function loadScript() {
  if (window.turnstile) return Promise.resolve();
  let tag = document.querySelector(`script[src="${SCRIPT_SRC}"]`);
  if (!tag) {
    tag = document.createElement("script");
    tag.src = SCRIPT_SRC;
    tag.async = true;
    document.head.appendChild(tag);
  }
  return new Promise((resolve) => tag.addEventListener("load", resolve, { once: true }));
}

export default function Captcha({ onToken }) {
  const ref = useRef(null);
  useEffect(() => {
    let widgetId;
    loadScript().then(() => {
      if (!ref.current) return;
      widgetId = window.turnstile.render(ref.current, {
        sitekey: SITE_KEY,
        callback: onToken,
        "expired-callback": () => onToken(""),
      });
    });
    return () => widgetId && window.turnstile?.remove(widgetId);
  }, [onToken]);
  return <div ref={ref} className="captcha" />;
}

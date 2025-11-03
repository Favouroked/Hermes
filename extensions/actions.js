// JavaScript

function doType(querySelector, value) {
  const el = document.querySelector(querySelector);
  if (!el) return false;
  el.focus();
  el.value = "";
  for (const ch of String(value)) {
    el.value += ch;
    el.dispatchEvent(new Event('input', { bubbles: true }));
  }
  el.dispatchEvent(new Event('change', { bubbles: true }));
  return true;
}

function doClick(querySelector) {
  const el = document.querySelector(querySelector);
  if (!el) return false;
  el.focus();
  el.click();
  return true;
}

function doSelect(querySelector, value) {
  const el = document.querySelector(querySelector);
  if (!el) return false;
  // Supports both <select> and inputs with datalist/custom handlers
  if (el.tagName === 'SELECT') {
    const opt = Array.from(el.options).find(o => o.value === value || o.text === value);
    if (opt) {
      el.value = opt.value;
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      return true;
    }
    return false;
  } else {
    el.focus();
    el.value = value;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  }
}
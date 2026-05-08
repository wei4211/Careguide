(function () {
  const sections = Array.from(document.querySelectorAll('.form-section'));
  const steps = Array.from(document.querySelectorAll('.step-indicator .step'));
  const prevBtn = document.getElementById('prevBtn');
  const nextBtn = document.getElementById('nextBtn');
  const submitBtn = document.getElementById('submitBtn');
  const form = document.getElementById('assessmentForm');

  if (!sections.length) return;

  const DRAFT_KEY = 'careguide.assessment.draft.v1';
  let current = 0;

  // ---- 草稿自動儲存 ----
  function saveDraft() {
    const data = {};
    new FormData(form).forEach((v, k) => { data[k] = v; });
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify({ data, ts: Date.now() }));
      showDraftStatus('草稿已自動儲存');
    } catch (e) { /* localStorage 滿了就放棄 */ }
  }

  function clearDraft() {
    try { localStorage.removeItem(DRAFT_KEY); } catch (e) {}
  }

  function restoreDraft() {
    let raw;
    try { raw = localStorage.getItem(DRAFT_KEY); } catch (e) { return; }
    if (!raw) return;

    let payload;
    try { payload = JSON.parse(raw); } catch (e) { return; }
    const data = payload.data || {};
    if (!Object.keys(data).length) return;

    // 7 天前的草稿視為過期
    if (payload.ts && Date.now() - payload.ts > 7 * 24 * 3600 * 1000) {
      clearDraft();
      return;
    }

    if (!confirm('偵測到先前未完成的問卷草稿，要還原嗎？\n（按取消會清除草稿、從頭開始）')) {
      clearDraft();
      return;
    }

    Object.entries(data).forEach(([name, value]) => {
      const fields = form.querySelectorAll(`[name="${name}"]`);
      fields.forEach(f => {
        if (f.type === 'radio' || f.type === 'checkbox') {
          f.checked = (f.value === value);
        } else {
          f.value = value;
        }
      });
    });
    showDraftStatus('已還原先前的草稿');
  }

  function showDraftStatus(text) {
    const el = document.getElementById('draftStatus');
    if (!el) return;
    el.textContent = text;
    el.classList.add('show');
    clearTimeout(showDraftStatus._t);
    showDraftStatus._t = setTimeout(() => el.classList.remove('show'), 1800);
  }

  let saveTimer;
  form.addEventListener('input', () => {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(saveDraft, 400);
  });
  form.addEventListener('change', () => {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(saveDraft, 200);
  });

  function show(index) {
    sections.forEach((s, i) => s.classList.toggle('d-none', i !== index));
    steps.forEach((s, i) => {
      s.classList.toggle('active', i === index);
      s.classList.toggle('done', i < index);
    });

    prevBtn.disabled = index === 0;

    const isLast = index === sections.length - 1;
    nextBtn.classList.toggle('d-none', isLast);
    submitBtn.classList.toggle('d-none', !isLast);

    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function validateCurrentStep() {
    const fields = sections[current].querySelectorAll('input[required], select[required]');
    for (const field of fields) {
      if (!field.value) {
        field.reportValidity();
        return false;
      }
    }
    return true;
  }

  nextBtn.addEventListener('click', () => {
    if (!validateCurrentStep()) return;
    if (current < sections.length - 1) {
      current += 1;
      show(current);
    }
  });

  prevBtn.addEventListener('click', () => {
    if (current > 0) {
      current -= 1;
      show(current);
    }
  });

  form.addEventListener('submit', (e) => {
    if (!validateCurrentStep()) {
      e.preventDefault();
      return;
    }
    clearDraft();  // 成功送出 → 清掉草稿
    submitBtn.disabled = true;
    submitBtn.textContent = '評估中…';

    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
      document.getElementById('loadingTitle').textContent = '系統評估中…';
      overlay.hidden = false;
    }
  });

  steps.forEach((step, i) => {
    step.addEventListener('click', () => {
      if (i < current) {
        current = i;
        show(current);
      }
    });
  });

  show(0);
  restoreDraft();
})();

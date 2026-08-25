const state = {
  meta: null,
  situation: null,
  counterpart: "",
  avoid: new Set(),
  topics: [],
  mode: 'scenario', // 'scenario' | 'news' | 'facts'
};

// 배포 환경에서는 Render 백엔드 URL, 로컬에선 상대경로
// window.API_BASE는 config.js에서 주입 (배포 시 생성)
const API_BASE = window.API_BASE || '';

async function fetchMeta() {
  try {
    const res = await fetch(`${API_BASE}/api/meta`);
    state.meta = await res.json();
    renderSituations();
    // 포트원 공개키 로드
    const cfgRes = await fetch(`${API_BASE}/api/config`);
    const cfg = await cfgRes.json();
    window.PORTONE_IMP_KEY = cfg.portone_imp_key || '';
  } catch (e) {
    console.error('메타 로드 실패', e);
  }
}

// 모드 전환
function hideScenarioSteps() {
  document.getElementById('step-situation').style.display = 'none';
  document.getElementById('step-counterpart').style.display = 'none';
  document.getElementById('step-avoid').style.display = 'none';
}

function selectMode(mode) {
  state.mode = mode;
  state.situation = null;      // 이전 선택 초기화
  state.counterpart = '';
  state.avoid.clear();
  // 칩 활성화
  document.getElementById('mode-scenario').classList.toggle('active', mode === 'scenario');
  document.getElementById('mode-news').classList.toggle('active', mode === 'news');
  document.getElementById('mode-facts').classList.toggle('active', mode === 'facts');
  // 상대·피할주제 칩의 active 해제
  document.querySelectorAll('#counterpart-chips .chip, #avoid-chips .chip')
    .forEach((c) => c.classList.remove('active'));
  document.querySelectorAll('.grid-item').forEach((el) => el.classList.remove('selected'));

  if (mode === 'facts') {
    hideScenarioSteps();
    generateFacts();
  } else if (mode === 'news') {
    hideScenarioSteps();
    generateNews();
  } else {
    // 시나리오 모드: 01만 표시, 결과 숨김, 리셋
    document.getElementById('step-situation').style.display = 'block';
    document.getElementById('step-counterpart').style.display = 'none';
    document.getElementById('step-avoid').style.display = 'none';
    document.getElementById('result').style.display = 'none';
    document.getElementById('loading').style.display = 'none';
    document.getElementById('step-situation').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

document.getElementById('mode-scenario').addEventListener('click', () => selectMode('scenario'));
document.getElementById('mode-news').addEventListener('click', () => selectMode('news'));
document.getElementById('mode-facts').addEventListener('click', () => selectMode('facts'));

function renderSituations() {
  const grid = document.getElementById('situation-grid');
  grid.innerHTML = '';
  for (const [key, s] of Object.entries(state.meta.situations)) {
    const el = document.createElement('div');
    el.className = 'grid-item';
    el.dataset.key = key;
    el.innerHTML = `
      <div class="icon">${s.icon || '💬'}</div>
      <div class="name">${s.label}</div>
      <div class="desc">${s.desc}</div>
    `;
    el.addEventListener('click', () => selectSituation(key));
    grid.appendChild(el);
  }
}

function selectSituation(key) {
  state.situation = key;
  document.querySelectorAll('.grid-item').forEach((el) => {
    el.classList.toggle('selected', el.dataset.key === key);
  });

  // 상대 칩 렌더 (상황별로 다름)
  const chipsBox = document.getElementById('counterpart-chips');
  chipsBox.innerHTML = '';
  const options = state.meta.situations[key].counterparts;
  options.forEach((c) => {
    const chip = document.createElement('span');
    chip.className = 'chip';
    chip.textContent = c;
    chip.addEventListener('click', () => selectCounterpart(chip, c));
    chipsBox.appendChild(chip);
  });

  // 피할 주제 칩 렌더
  const avoidBox = document.getElementById('avoid-chips');
  avoidBox.innerHTML = '';
  for (const [k, label] of Object.entries(state.meta.allergies)) {
    const chip = document.createElement('span');
    chip.className = 'chip';
    chip.dataset.key = k;
    chip.textContent = label;
    chip.addEventListener('click', () => toggleAvoid(chip, k));
    avoidBox.appendChild(chip);
  }

  document.getElementById('step-counterpart').style.display = 'block';
  document.getElementById('step-avoid').style.display = 'block';
  document.getElementById('step-counterpart').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function selectCounterpart(el, val) {
  [...el.parentElement.children].forEach((c) => c.classList.remove('active'));
  el.classList.add('active');
  state.counterpart = val;
}

function toggleAvoid(el, key) {
  if (state.avoid.has(key)) {
    state.avoid.delete(key);
    el.classList.remove('active');
  } else {
    state.avoid.add(key);
    el.classList.add('active');
  }
}

async function generateNews() {
  document.getElementById('result').style.display = 'none';
  document.getElementById('loading').style.display = 'block';
  document.getElementById('loading').scrollIntoView({ behavior: 'smooth' });
  try {
    const res = await fetch(`${API_BASE}/api/news?n=5`);
    const data = await res.json();
    state.topics = data.topics;
    renderResult(data, true);
  } catch (e) {
    alert('화제를 불러오지 못했어요.');
    document.getElementById('loading').style.display = 'none';
  }
}

// 결제 상태 확인 (기기 단위, localStorage)
function isUnlocked() {
  return !!localStorage.getItem('smtk_unlocked');
}

async function generateFacts() {
  document.getElementById('result').style.display = 'none';
  document.getElementById('loading').style.display = 'block';
  document.getElementById('loading').scrollIntoView({ behavior: 'smooth' });
  try {
    const res = await fetch(`${API_BASE}/api/facts?n=5`);
    const data = await res.json();
    state.topics = data.topics;
    // fact 카드 제목을 걸러 금지어 적용(간단히) — MVP는 그대로 표시
    renderResult(data, true);
  } catch (e) {
    alert('화제를 불러오지 못했어요.');
    document.getElementById('loading').style.display = 'none';
  }
}

async function generate() {
  if (!state.situation) return alert('① 상황을 먼저 선택해 주세요');
  if (!state.counterpart) return alert('② 상대를 선택해 주세요');

  const btn = document.getElementById('generate-btn');
  btn.disabled = true;
  document.getElementById('result').style.display = 'none';
  document.getElementById('loading').style.display = 'block';
  document.getElementById('loading').scrollIntoView({ behavior: 'smooth' });

  try {
    const qs = new URLSearchParams({
      situation: state.situation,
      counterpart: state.counterpart,
      avoid: [...state.avoid].join(','),
    });
    const res = await fetch(`${API_BASE}/api/generate?${qs}`);
    let data = await res.json();
    state.topics = data.topics;
    // 결제 완료 기기라면 전체 공개
    if (isUnlocked()) {
      state.topics.forEach((t) => { t.locked = false; });
      data = {
        ...data,
        topics: state.topics,
        free_count: state.topics.length,
        premium_count: 0,
      };
    }
    renderResult(data);
  } catch (e) {
    alert('생성에 실패했어요. 잠시 후 다시 시도해 주세요.');
    document.getElementById('loading').style.display = 'none';
  } finally {
    btn.disabled = false;
  }
}

function renderResult(data, isFacts = false) {
  const box = document.getElementById('topics');
  box.innerHTML = '';
  const unlocked = isUnlocked(); // 결제 기기는 모든 조합도 전체 공개
  data.topics.forEach((t) => {
    if (unlocked && t.locked) t.locked = false;
    const div = document.createElement('div');
    div.className = t.locked ? 'topic locked' : 'topic';
    // 뉴스/위키백과 화제 카드: 핵심 요약 + 링크
    const isFactLike = !!t.url;
    const bodyHtml = isFactLike ? `
      <p class="fact-hook">💬 ${escapeHtml(t.hook || '')}</p>
      <details class="fact-details">
        <summary>더 알아보기</summary>
        <p class="fact-summary">${escapeHtml(t.summary || '링크에서 확인해 보세요.')}</p>
      </details>
      <a class="fact-src" href="${escapeHtml(t.url)}" target="_blank" rel="noopener">기사 보기 🔗</a>
    ` : '';
    div.innerHTML = `
      <h3>${escapeHtml((t.source_name ? `[${t.source_name}] ` : '') + t.title)}</h3>
      ${!t.locked && t.opener && !t.url ? `<p class="opener-line">🗨️ ${escapeHtml(t.opener)}</p>` : ''}
      ${!t.locked && t.followups?.length && !t.url ? `<ul>${t.followups.map((f) => `<li>${escapeHtml(f)}</li>`).join('')}</ul>` : ''}
      ${!t.locked ? bodyHtml : ''}
      ${t.locked ? `
        <div class="lock-overlay">
          <div class="lock-icon">🔒</div>
          <p>프리미엄 주제</p>
        </div>
      ` : ''}
    `;
    box.appendChild(div);
  });

  // 배지·CTA는 결제 상태 반영해 표시
  if (unlocked) {
    document.getElementById('free-badge').textContent =
      `✓ 프리미엄 해제됨 · 전체 ${data.topics.length}개 공개`;
  } else {
    const freeN = data.topics.filter((t) => !t.locked).length;
    const lockedN = data.topics.length - freeN;
    document.getElementById('free-badge').textContent =
      `무료 ${freeN}개 공개 · 프리미엄 ${lockedN}개 잠김`;
  }

  if (!unlocked && !isFacts && data.premium_count > 0) {
    document.getElementById('locked-count').textContent = data.premium_count;
    document.getElementById('premium-cta').style.display = 'block';
  } else {
    document.getElementById('premium-cta').style.display = 'none';
  }

  const tipsList = document.getElementById('tips-list');
  tipsList.innerHTML = '';
  const tips = data.tips || [
    '질문 후 상대의 말을 반복하며 공감 먼저 하기',
    '내 경험도 한 문장씩 곁들이며 왕복 대화 만들기',
  ];
  (tips || []).forEach((t) => {
    const li = document.createElement('li');
    li.textContent = t;
    tipsList.appendChild(li);
  });

  document.getElementById('loading').style.display = 'none';
  document.getElementById('result').style.display = 'block';
  document.getElementById('result').scrollIntoView({ behavior: 'smooth' });
}

async function unlockPremium() {
  const btn = document.getElementById('unlock-btn');
  btn.disabled = true;
  btn.textContent = '⏳ 결제 준비 중...';

  try {
    // 1) 주문번호 발급
    const orderRes = await fetch(`${API_BASE}/api/order/new`);
    const order = await orderRes.json();
    if (!order.merchant_uid) throw new Error('주문번호 발급 실패');

    // 2) 포트원 초기화 — 키 없으면 데모 모드
    const impKey = window.PORTONE_IMP_KEY || '';
    if (impKey && window.IMP) {
      window.IMP.init(impKey);

      // 3) 결제창 호출 (테스트 PG)
      await new Promise((resolve, reject) => {
        window.IMP.request_pay({
          pg: 'kakaopay', // 테스트: 카카오페이
          pay_method: 'card',
          merchant_uid: order.merchant_uid,
          name: '스몰토크 프리미엄 해제',
          amount: order.amount,
          buyer_name: '스몰토크 사용자',
        }, async (rsp) => {
          if (rsp.success) {
            // 4) 서버 검증
            try {
              const vRes = await fetch(`${API_BASE}/api/verify`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ imp_uid: rsp.imp_uid, merchant_uid: rsp.merchant_uid }),
              });
              const vData = await vRes.json();
              if (vData.success) {
                localStorage.setItem('smtk_unlocked', vData.unlock_token);
                resolve(vData);
              } else {
                reject(new Error(vData.message || '검증 실패'));
              }
            } catch (e) { reject(e); }
          } else {
            reject(new Error(rsp.error_msg || '결제 취소'));
          }
        });
      });
    } else {
      // 데모 모드: PG 키 미설정 → 서버 스텁으로 즉시 해제
      const res = await fetch(`${API_BASE}/api/unlock`, { method: 'POST' });
      const data = await res.json();
      if (!data.success) throw new Error(data.message);
      localStorage.setItem('smtk_unlocked', `demo_${Date.now()}`);
    }

    // 5) 잠금 해제 렌더링
    state.topics.forEach((t) => { t.locked = false; });
    renderResult({
      topics: state.topics,
      free_count: state.topics.length,
      premium_count: 0,
      tips: Array.from(document.querySelectorAll('#tips-list li')).map((li) => li.textContent),
    }, true);
  } catch (e) {
    alert(e.message || '결제에 실패했어요.');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '🔓 900원으로 전체 열기';
  }
}

function escapeHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

document.getElementById('generate-btn').addEventListener('click', generate);
// 현재 모드에 맞는 재생성
document.getElementById('again-btn').addEventListener('click', () => {
  if (state.mode === 'news') generateNews();
  else if (state.mode === 'facts') generateFacts();
  else generate();
});
document.getElementById('unlock-btn').addEventListener('click', unlockPremium);

fetchMeta();

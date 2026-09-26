async function fetchStatus() {
  try {
    const res = await fetch('/api/status');
    if (res.ok) {
      const data = await res.json();
      renderDashboard(data);
    }
  } catch (err) {
    console.error('Error loading AIOps status:', err);
  }
}

function renderDashboard(data) {
  const score = data.current_score !== undefined ? data.current_score : 100;
  const scoreEl = document.getElementById('health-score');
  const pathEl = document.getElementById('score-path');
  const statusText = document.getElementById('score-status-text');

  scoreEl.textContent = score;
  pathEl.setAttribute('stroke-dasharray', score + ', 100');

  if (score >= 90) {
    scoreEl.style.backgroundImage = 'linear-gradient(135deg, #10b981, #06b6d4)';
    pathEl.style.stroke = '#10b981';
    statusText.textContent = 'Estável & Saudável';
    statusText.style.color = '#10b981';
  } else if (score >= 70) {
    scoreEl.style.backgroundImage = 'linear-gradient(135deg, #f59e0b, #f97316)';
    pathEl.style.stroke = '#f59e0b';
    statusText.textContent = 'Atenção: Risco Detectado';
    statusText.style.color = '#f59e0b';
  } else {
    scoreEl.style.backgroundImage = 'linear-gradient(135deg, #f43f5e, #e11d48)';
    pathEl.style.stroke = '#f43f5e';
    statusText.textContent = 'Crítico: Ação Preventiva Necessária';
    statusText.style.color = '#f43f5e';
  }

  const predictions = data.predictions || [];
  const anomalies = data.anomalies || [];
  const insights = data.insights || [];
  const logs = data.log_errors || [];

  document.getElementById('risks-count').textContent = predictions.length;
  document.getElementById('anomalies-count').textContent = anomalies.length;
  document.getElementById('insights-count').textContent = insights.length;
  document.getElementById('risks-badge').textContent = predictions.length + ' Ativos';

  // Insights (Gemini RCA)
  const insList = document.getElementById('insights-list');
  if (insights.length === 0) {
    insList.innerHTML = '<div class="empty-state">O motor de IA (Gemini) está monitorando continuamente. Nenhum incidente crítico pendente.</div>';
  } else {
    insList.innerHTML = insights.map(function(i) {
      return '<div class="rca-box">' +
        '<div class="rca-title">🎯 ' + (i.title || 'Diagnóstico de Causa Raiz') + '</div>' +
        '<div class="rca-cause"><strong>Causa Raiz:</strong> ' + (i.probable_root_cause || '') + '</div>' +
        (i.recommended_action ? '<div class="rca-action"><strong>Comando Sugerido:</strong> ' + i.recommended_action + '</div>' : '') +
        (i.prevention_playbook && i.prevention_playbook.length ? '<ul class="playbook-steps">' + i.prevention_playbook.map(function(s) { return '<li>• ' + s + '</li>'; }).join('') + '</ul>' : '') +
      '</div>';
    }).join('');
  }

  // Predictions (ML)
  const predList = document.getElementById('predictions-list');
  if (predictions.length === 0) {
    predList.innerHTML = '<div class="empty-state">Nenhum risco preditivo detectado. Memória e storage operando dentro das margens ideais.</div>';
  } else {
    predList.innerHTML = predictions.map(function(p) {
      const sev = p.severity ? p.severity.toLowerCase() : 'warning';
      return '<div class="item-card ' + sev + '">' +
        '<div class="item-header">' +
          '<span class="item-title">' + (p.message || p.type) + '</span>' +
          (p.estimated_minutes_to_failure ? '<span class="item-time">⏱️ Falha em ' + p.estimated_minutes_to_failure + ' min</span>' : '') +
        '</div>' +
        '<div class="item-body">' +
          '<strong>Recomendação:</strong> ' + (p.recommendation || 'Verificar telemetria do pod.') +
        '</div>' +
        '<div class="item-footer">' +
          '<span class="item-tag">' + p.namespace + ' / ' + (p.pod || p.service || p.pvc) + '</span>' +
          '<button class="btn btn-sm btn-warn" onclick="remediateRisk(\'' + p.id + '\')">🛡️ Auto-Remediar</button>' +
        '</div>' +
      '</div>';
    }).join('');
  }

  // Anomalies
  const anomList = document.getElementById('anomalies-list');
  if (anomalies.length === 0) {
    anomList.innerHTML = '<div class="empty-state">Latência e taxas de erro HTTP dentro das metas de SLO.</div>';
  } else {
    anomList.innerHTML = anomalies.map(function(a) {
      const sev = a.severity ? a.severity.toLowerCase() : 'critical';
      return '<div class="item-card ' + sev + '">' +
        '<div class="item-header">' +
          '<span class="item-title">' + (a.message || a.type) + '</span>' +
          '<span class="item-time">' + a.current_value + ' ' + (a.unit || '') + '</span>' +
        '</div>' +
        '<div class="item-footer">' +
          '<span class="item-tag">' + a.namespace + ' / ' + a.service + '</span>' +
        '</div>' +
      '</div>';
    }).join('');
  }

  // Logs
  const logsList = document.getElementById('logs-list');
  if (logs.length === 0) {
    logsList.innerHTML = '<div class="empty-state">Nenhum log de erro recente nos pods monitorados.</div>';
  } else {
    logsList.innerHTML = logs.map(function(l) {
      return '<div class="log-entry">' +
        '<span class="log-ns">[' + l.namespace + '/' + l.pod + ']</span> ' + l.log +
      '</div>';
    }).join('');
  }
}

async function triggerAnalysis() {
  const icon = document.getElementById('refresh-icon');
  icon.textContent = '⏳';
  try {
    const res = await fetch('/api/analyze-now', { method: 'POST' });
    if (res.ok) {
      await fetchStatus();
runConnectivityTest();
fetchPostMortems();
    }
  } finally {
    icon.textContent = '⚡';
  }
}

async function simulate(scenario) {
  try {
    const res = await fetch('/api/simulate-anomaly', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario: scenario })
    });
    if (res.ok) {
      await fetchStatus();
runConnectivityTest();
fetchPostMortems();
    }
  } catch (err) {
    console.error('Simulation error:', err);
  }
}

async function sendTestSlack() {
  try {
    const res = await fetch('/api/send-test-slack', { method: 'POST' });
    const data = await res.json();
    if (data.slack_delivered) {
      alert('🔔 Alerta enviado com sucesso para o Slack!');
    } else {
      alert('⚠️ Webhook do Slack disparado (verifique as permissões do webhook).');
    }
  } catch (err) {
    alert('Erro ao enviar mensagem para o Slack: ' + err);
  }
}

async function resetSimulation() {
  await triggerAnalysis();
}

async function remediateRisk(riskId) {
  try {
    const res = await fetch('/api/remediate/' + riskId, { method: 'POST' });
    if (res.ok) {
      alert('Ação de Auto-Remediação executada com sucesso!');
      await fetchStatus();
runConnectivityTest();
fetchPostMortems();
    }
  } catch (err) {
    alert('Erro ao executar remediação: ' + err);
  }
}

fetchStatus();
runConnectivityTest();
fetchPostMortems();
setInterval(fetchStatus, 3000);
setInterval(fetchPostMortems, 5000);
// Connectivity Test Functions
async function runConnectivityTest() {
  const icon = document.getElementById('test-conn-icon');
  if (icon) icon.textContent = '⏳';
  try {
    const res = await fetch('/api/connectivity-test');
    if (res.ok) {
      const data = await res.json();
      updateConnectivityBadges(data);
    }
  } catch (err) {
    console.error('Error testing connectivity:', err);
  } finally {
    if (icon) icon.textContent = '⚡';
  }
}

function updateConnectivityBadges(diag) {
  if (!diag) return;

  function setBadge(id, svcName, info) {
    const el = document.getElementById(id);
    if (!el) return;
    el.className = 'badge-conn ' + (info.status || 'unknown');
    const val = el.querySelector('.badge-val');
    if (val) {
      if (info.status === 'healthy') {
        val.textContent = 'Online (' + (info.latency_ms || 0) + 'ms)';
      } else if (info.status === 'disabled') {
        val.textContent = 'Fallback Ativo';
      } else if (info.status === 'not_configured') {
        val.textContent = 'Não configurado';
      } else {
        val.textContent = 'Falha (' + (info.latency_ms || 0) + 'ms)';
      }
    }
    el.title = info.message || '';
  }

  if (diag.loki) setBadge('badge-loki', 'Loki', diag.loki);
  if (diag.prometheus) setBadge('badge-prom', 'Prometheus', diag.prometheus);
  if (diag.kubernetes) setBadge('badge-k8s', 'Kubernetes', diag.kubernetes);
  if (diag.gemini) setBadge('badge-gemini', 'Gemini', diag.gemini);
  if (diag.slack) setBadge('badge-slack', 'Slack', diag.slack);
}

async function fetchPostMortems() {
  try {
    const res = await fetch('/api/post-mortems');
    if (res.ok) {
      const pms = await res.json();
      renderPostMortems(pms);
    }
  } catch (err) {
    console.error('Error loading post-mortems:', err);
  }
}

function renderPostMortems(pms) {
  const listEl = document.getElementById('postmortems-list');
  const badgeEl = document.getElementById('pm-badge');
  if (!listEl) return;

  if (badgeEl) badgeEl.textContent = pms.length + ' Relatórios';

  if (!pms || pms.length === 0) {
    listEl.innerHTML = '<div class="empty-state">Nenhum Post-Mortem registrado. Quando o cluster atinge Health Score >= 95 após um incidente, o relatório completo sintetizado pelo Google Gemini é publicado aqui e enviado ao Slack.</div>';
    return;
  }

  listEl.innerHTML = pms.map(function(pm) {
    const actions = (pm.action_items || []).map(function(a) { return '<li>' + a + '</li>'; }).join('');
    return '<div class="pm-box">' +
      '<div class="pm-header">' +
        '<div class="pm-title">📋 ' + (pm.title || 'Post-Mortem Oficial') + '</div>' +
        '<div class="pm-meta">' +
          '<span class="pm-tag">✅ ' + (pm.status || 'RESOLVED') + '</span>' +
          '<span class="pm-tag">⏱️ MTTR: ' + (pm.mttr_formatted || pm.mttr_minutes + 'm') + '</span>' +
          '<span class="pm-tag">🎯 Score: ' + (pm.final_score || 100) + '/100</span>' +
        '</div>' +
      '</div>' +
      '<div class="pm-summary">' + (pm.executive_summary || '') + '</div>' +
      '<div class="pm-grid">' +
        '<div class="pm-block">' +
          '<h4>🔍 Causa Raiz Técnica (Gemini AI)</h4>' +
          '<p>' + (pm.root_cause_analysis || 'N/A') + '</p>' +
        '</div>' +
        '<div class="pm-block">' +
          '<h4>🛠️ Remediação que Estabilizou o Cluster</h4>' +
          '<p>' + (pm.remediation_details || 'N/A') + '</p>' +
        '</div>' +
      '</div>' +
      (actions ? '<div class="pm-block pm-actions" style="margin-top:6px;">' +
        '<h4>🛡️ Ações Preventivas (Action Items)</h4>' +
        '<ul>' + actions + '</ul>' +
      '</div>' : '') +
    '</div>';
  }).join('');
}

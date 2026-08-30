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
    }
  } catch (err) {
    alert('Erro ao executar remediação: ' + err);
  }
}

fetchStatus();
setInterval(fetchStatus, 3000);
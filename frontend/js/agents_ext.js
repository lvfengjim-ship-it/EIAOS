// EIAOS Agent 扩展客户端 — 覆盖全部 11 个模块
// 用法：在 index.html 中，原有 agents.js 之后引入本文件
//   <script src="frontend/js/agents.js"></script>
//   <script src="frontend/js/agents_ext.js"></script>

// 通用运行器：任意 Agent + 结果渲染 + 待激活(423)提示
async function runAgentUI(agentType, inputData, resultElId, btnSelector) {
    const btn = btnSelector ? document.querySelector(btnSelector) : null;
    const resultEl = document.getElementById(resultElId);

    if (btn) { btn.disabled = true; btn.dataset.origText = btn.textContent; btn.textContent = '运行中...'; }

    try {
        const task = await window.agentRunner.runAgent(agentType, inputData);

        window.agentRunner.pollTask(task.task_id,
            (progress) => { if (btn) btn.textContent = `运行中... ${progress.status}`; },
            (out) => {
                if (btn) { btn.disabled = false; btn.textContent = btn.dataset.origText; }
                if (!resultEl) return;
                const r = out.result || {};
                if (out.error || r.error) {
                    resultEl.innerHTML = `<div style="color:red">错误: ${out.error || r.error}</div>`;
                } else {
                    let html = `<pre style="white-space:pre-wrap">${r.result || JSON.stringify(out, null, 2)}</pre>`;
                    if (r.report_file) html += `<div style="color:#888;font-size:12px">报告已保存: ${r.report_file}</div>`;
                    resultEl.innerHTML = html;
                }
                resultEl.style.display = 'block';
            }
        );
        return task;
    } catch (e) {
        if (btn) { btn.disabled = false; btn.textContent = btn.dataset.origText; }
        // 423 = Agent 待激活
        if (e.message && e.message.includes('agent_pending')) {
            alert('该 Agent 尚未激活，请在 agents.yaml 中将 status 改为 active');
        } else {
            alert('错误: ' + e.message);
        }
        throw e;
    }
}

// ------- 各模块便捷函数 -------

// 政策监测（手动分析）
function runPolicyMonitor(policyText, region) {
    return runAgentUI('policy_monitor',
        { mode: 'analyze', policy_text: policyText, region: region },
        'result-policy', '[data-agent="policy_monitor"]');
}

// 投资初筛
function runInvestmentScreening(project) {
    return runAgentUI('investment_screening', project,
        'result-investment', '[data-agent="investment_screening"]');
}

// 财务建模
function runFinancialModel(params) {
    return runAgentUI('financial_model', params,
        'result-financial', '[data-agent="financial_model"]');
}

// GIS 选址
function runGISSelection(sites, projectType) {
    return runAgentUI('gis_site_selection',
        { candidate_sites: sites, project_type: projectType },
        'result-gis', '[data-agent="gis_site_selection"]');
}

// 电力市场
function runPowerMarket(marketData, province, reportType) {
    return runAgentUI('power_market',
        { market_data: marketData, province: province, report_type: reportType || 'weekly' },
        'result-market', '[data-agent="power_market"]');
}

// EMS 运行报告
function runEMSReport(stationName, date, telemetry) {
    return runAgentUI('ems_report',
        { station_name: stationName, date: date, telemetry: telemetry },
        'result-ems', '[data-agent="ems_report"]');
}

// 知识库：查询
function runKnowledgeQuery(question, topK) {
    return runAgentUI('knowledge_base',
        { action: 'query', question: question, top_k: topK || 5 },
        'result-knowledge', '[data-agent="knowledge_base"]');
}

// 知识库：文档入库
function runKnowledgeIngest(documents) {
    return runAgentUI('knowledge_base',
        { action: 'ingest', documents: documents },
        'result-knowledge', '[data-agent="knowledge_base"]');
}

// 待激活模块（调用会收到 423 + 激活指引）
function runRiskAgent(projectInfo)    { return runAgentUI('risk_agent',    { project_info: projectInfo },    'result-risk',     '[data-agent="risk_agent"]'); }
function runLegalAgent(contractText)  { return runAgentUI('legal_agent',   { contract_text: contractText },  'result-legal',    '[data-agent="legal_agent"]'); }
function runCarbonAgent(generationMwh, period) { return runAgentUI('carbon_agent', { generation_mwh: generationMwh, period: period }, 'result-carbon', '[data-agent="carbon_agent"]'); }
function runHydrogenAgent(projectInfo){ return runAgentUI('hydrogen_agent',{ project_info: projectInfo },    'result-hydrogen', '[data-agent="hydrogen_agent"]'); }

// 页面加载时拉取 Agent 清单，自动把 pending 的按钮置灰并标注
document.addEventListener('DOMContentLoaded', async () => {
    try {
        const { agents } = await window.agentRunner.listAgents();
        agents.forEach(a => {
            const btn = document.querySelector(`[data-agent="${a.id}"]`);
            if (btn && a.status === 'pending') {
                btn.disabled = true;
                btn.textContent = `${btn.textContent}（待激活）`;
                btn.title = (a.activation_requirements || []).join('\n');
            }
        });
    } catch (e) {
        console.warn('Agent 清单加载失败（后端未启动？）', e);
    }
});

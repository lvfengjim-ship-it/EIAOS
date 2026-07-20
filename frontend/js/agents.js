// EIAOS Agent 运行客户端
class AgentRunner {
    constructor() {
        this.baseUrl = 'http://localhost:8000/api';
        this.activeTasks = new Map();
    }

    async listAgents() {
        const resp = await fetch(`${this.baseUrl}/agents/`);
        if (!resp.ok) throw new Error('获取 Agent 列表失败');
        return await resp.json();
    }

    async runAgent(agentType, inputData) {
        const resp = await fetch(`${this.baseUrl}/agents/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                agent_type: agentType,
                input_data: inputData
            })
        });

        if (!resp.ok) {
            const error = await resp.json();
            throw new Error(typeof error.detail === 'string' ? error.detail : JSON.stringify(error.detail));
        }

        const result = await resp.json();
        return result;
    }

    async getTaskStatus(taskId) {
        const resp = await fetch(`${this.baseUrl}/agents/run/${taskId}`);
        return await resp.json();
    }

    async pollTask(taskId, onProgress, onComplete, interval = 3000) {
        const check = async () => {
            try {
                const status = await this.getTaskStatus(taskId);

                if (status.status === 'completed') {
                    onComplete(status);
                } else if (status.status === 'failed') {
                    onComplete({ error: status.error || '任务失败' });
                } else {
                    onProgress(status);
                    setTimeout(check, interval);
                }
            } catch (e) {
                console.error('轮询错误:', e);
                setTimeout(check, interval * 2);
            }
        };
        check();
    }
}

// 全局实例
window.agentRunner = new AgentRunner();

// 便捷函数
async function runInvestmentAgent(projectData) {
    const btn = document.querySelector('[data-agent="investment"]');
    if (btn) {
        btn.disabled = true;
        btn.textContent = '分析中...';
    }

    try {
        const task = await window.agentRunner.runAgent('investment', projectData);

        window.agentRunner.pollTask(task.task_id,
            (progress) => {
                if (btn) btn.textContent = `分析中... ${progress.status}`;
            },
            (result) => {
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = '运行投资分析';
                }

                const resultEl = document.getElementById('result-investment');
                if (resultEl) {
                    if (result.error) {
                        resultEl.innerHTML = `<div style="color:red">错误: ${result.error}</div>`;
                    } else {
                        resultEl.innerHTML = `<pre style="white-space:pre-wrap">${result.result?.result || JSON.stringify(result, null, 2)}</pre>`;
                    }
                    resultEl.style.display = 'block';
                }
            }
        );

        return task;
    } catch (e) {
        if (btn) {
            btn.disabled = false;
            btn.textContent = '运行投资分析';
        }
        alert('错误: ' + e.message);
        throw e;
    }
}

async function runPolicyAgent(policyTopic) {
    const task = await window.agentRunner.runAgent('policy', { policy_topic: policyTopic });

    window.agentRunner.pollTask(task.task_id,
        () => {},
        (result) => {
            const resultEl = document.getElementById('result-policy');
            if (resultEl) {
                resultEl.innerHTML = `<pre style="white-space:pre-wrap">${result.result?.result || JSON.stringify(result, null, 2)}</pre>`;
                resultEl.style.display = 'block';
            }
        }
    );

    return task;
}

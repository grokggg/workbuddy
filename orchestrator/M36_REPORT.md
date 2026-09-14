# M36 报告 — 多格式云端破解 + 完整闭环

## 一、极狐 CI 多格式分派(实测 SUCCESS)

**pipeline #5489298: success**(78ad8023, 含 inbox/mc1 上传)

```
process job 实测:
  目标: inbox/mc1          ← 上传文件被自动识别
  格式: ELF               ← 自动分派
  分析: target=inbox/mc1  ← 统一分析执行
  3 job(process/llm/package) 全 success
```

上传即处理闭环: **放文件到 inbox/ → push → pipeline 自动跑 → pull 拿结果**

## 二、交付清单

### 上传闭环
- `orchestrator/trigger_upload.py` — 一条命令: copy→push→轮询→pull
- `orchestrator/batch_ci.py` — 多目标批量 + GitHub 搜索下载候选

### 多格式分派
- `.gitlab-ci.yml` — 3 stage(process/llm/package), 自动检测 ELF/PE/ASAR/OTHER

### LLM CI 集成
- llm stage: llm_engine 策略生成, 无 API key 降级规则版

### Oracle 后端
- `backends/setup_oracle.sh` — 一键装全套工具
- `backends/deploy_to_oracle.sh` — 一键部署工具链
- `backends/remote_run.py` — SSH 远程执行

### Docker 后端
- `backends/Dockerfile` + `docker-compose.yml` + `build_and_run.sh`(本机可用时执行)

## 三、实测结果

| 项 | 结果 |
|---|---|
| 极狐 CI 多格式 | ✅ pipeline #5489298 success |
| 上传即处理 | ✅ inbox/mc1 被自动识别处理 |
| 格式分派 | ✅ ELF 检测正确 |
| LLM stage | ✅ 执行(规则降级) |
| Docker 实测 | ⚠️ 沙箱无 docker(脚本就绪, 用户本机跑) |
| Oracle | 📋 脚本就绪(需用户注册) |

## 四、测试

- test_m36: 7 例全绿(ci 分派/上传/批量/oracle 脚本/docker 文件)

## 五、边界

- 沙箱无 docker: build_and_run.sh 需用户本机执行
- Oracle 需用户注册 + 填 IP
- LLM 无 API key: 规则推理降级(M33 llm_symbolic)

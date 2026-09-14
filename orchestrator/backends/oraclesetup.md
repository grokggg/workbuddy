# Oracle Cloud 后端设置指南(oraclesetup.md)

> M35: 长期兜底后端 —— Oracle Cloud 免费 ARM VM
> 免费额度: 4 OCPU + 24GB RAM(Always Free), 永久免费

## 一、注册

1. 访问 https://www.oracle.com/cloud/free/ 注册
2. 需要: 邮箱 + 手机 + 信用卡(仅验证, 不扣费)
3. 选择 "Always Free" 套餐

## 二、创建 ARM VM

1. 控制台 → 计算 → 实例 → 创建实例
2. 镜像: Ubuntu 22.04
3. 形状: **VM.Standard.A1.Flex**(ARM, Always Free)
   - OCPU: 4
   - 内存: 24GB
4. 网络: 默认 VCN + 开放 22 端口
5. **密钥**: 创建时生成 SSH 密钥对, 保存私钥到本机 `~/.ssh/oracle_arm`

## 三、SSH 配置

```bash
chmod 600 ~/.ssh/oracle_arm
ssh -i ~/.ssh/oracle_arm ubuntu@<公网IP>
# 验证: uname -m  # 应输出 aarch64
```

## 四、装全套工具(一次性)

```bash
sudo apt-get update
sudo apt-get install -y gcc gdb binutils python3-pip
pip3 install capstone pyelftools pefile angr unicorn
# 验证
python3 -c "import angr, unicorn, capstone; print('all OK')"
```

## 五、克隆工具链

```bash
git clone https://jihulab.com/Grantgust123/up-tools.git ~/up-tools
# 或
git clone https://github.com/grokggg/workbuddy.git ~/up-tools
cd ~/up-tools
```

## 六、用 oracle_cloud.py 对接

```bash
export ORACLE_HOST="<公网IP>"
export ORACLE_SSH_KEY="~/.ssh/oracle_arm"
export ORACLE_USER="ubuntu"

# 首次: 远程装工具
python3 orchestrator/backends/oracle_cloud.py --setup

# 跑分析(自动上传+远程执行)
python3 orchestrator/backends/oracle_cloud.py --run real-binaries/crackme-angr
```

## 七、额度说明

- Always Free: 无时间限制, 4 OCPU 24GB 永久
- ARM VM 比 x86 慢(编译 angr 约 15-20 分钟, 首次)
- 日常分析(纯 Python)跑得快, 适合长期批量

## 八、与后端切换器集成

```json
// config_backends.json
"oracle": {"host": "<公网IP>", "key_env": "ORACLE_SSH_KEY", "user": "ubuntu"}
```

backend_manager 检测 ORACLE_HOST 配置后自动可用。
